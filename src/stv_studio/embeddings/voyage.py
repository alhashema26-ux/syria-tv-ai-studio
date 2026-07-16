"""
Voyage AI Embeddings Provider
==============================
يحوّل النصوص إلى vectors (embeddings) عبر Voyage AI.
تُستخدم لبناء قاعدة البحث الدلالي في ChromaDB.
"""

import time
from typing import Literal

import voyageai
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)


class VoyageEmbeddings:
    """
    Provider للـ Voyage AI Embeddings.
    
    الاستخدام:
        embedder = VoyageEmbeddings(api_key="pa-...")
        vectors = embedder.embed_documents(["نص 1", "نص 2"])
        query_vec = embedder.embed_query("عنوان بحث")
    """
    
    # الأسعار (يوليو 2026)
    # voyage-3: $0.06 / 1M tokens
    PRICING_PER_1M_TOKENS = {
        "voyage-3": 0.06,
        "voyage-3-lite": 0.02,
        "voyage-3-large": 0.18,
        "voyage-code-3": 0.18,
    }
    
    # الحد الأقصى لعدد النصوص في request واحد
    MAX_BATCH_SIZE = 128
    
    def __init__(
        self,
        api_key: str,
        model: str = "voyage-3",
    ):
        """
        Args:
            api_key: مفتاح Voyage AI
            model: اسم النموذج (voyage-3 هو الافتراضي)
        """
        if not api_key:
            raise ValueError("Voyage API key is required")
        
        self.model = model
        self.client = voyageai.Client(api_key=api_key)
        
        # تتبع الإحصائيات
        self.total_tokens: int = 0
        self.total_cost: float = 0.0
        self.total_calls: int = 0
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _embed_batch(
        self,
        texts: list[str],
        input_type: Literal["document", "query"],
    ) -> tuple[list[list[float]], int]:
        """
        داخلي: توليد embeddings لدفعة واحدة.
        
        Args:
            texts: قائمة نصوص (حتى 128)
            input_type: "document" للتخزين، "query" للبحث
        
        Returns:
            (embeddings, tokens_used)
        """
        if len(texts) > self.MAX_BATCH_SIZE:
            raise ValueError(
                f"Batch size {len(texts)} exceeds max {self.MAX_BATCH_SIZE}"
            )
        
        response = self.client.embed(
            texts=texts,
            model=self.model,
            input_type=input_type,
        )
        
        embeddings = response.embeddings
        tokens = response.total_tokens
        
        return embeddings, tokens
    
    def embed_documents(
        self,
        texts: list[str],
        batch_size: int = 128,
        show_progress: bool = True,
    ) -> list[list[float]]:
        """
        توليد embeddings لمجموعة كبيرة من النصوص للتخزين.
        
        Args:
            texts: قائمة النصوص المراد تحويلها
            batch_size: حجم كل دفعة (max 128)
            show_progress: طباعة تقدم التنفيذ
        
        Returns:
            قائمة embeddings (كل embedding هو list[float] بطول 1024)
        """
        if not texts:
            return []
        
        batch_size = min(batch_size, self.MAX_BATCH_SIZE)
        all_embeddings = []
        
        total_batches = (len(texts) + batch_size - 1) // batch_size
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            batch_num = i // batch_size + 1
            
            start_time = time.perf_counter()
            embeddings, tokens = self._embed_batch(batch, input_type="document")
            elapsed = time.perf_counter() - start_time
            
            # تحديث الإحصائيات
            self.total_tokens += tokens
            self.total_calls += 1
            cost = (tokens / 1_000_000) * self.PRICING_PER_1M_TOKENS.get(self.model, 0.06)
            self.total_cost += cost
            
            all_embeddings.extend(embeddings)
            
            if show_progress:
                progress_pct = (batch_num / total_batches) * 100
                print(
                    f"  Batch {batch_num}/{total_batches} "
                    f"({progress_pct:.1f}%) - "
                    f"{len(batch)} texts, {tokens} tokens, "
                    f"{elapsed:.2f}s, ${cost:.6f}"
                )
        
        return all_embeddings
    
    def embed_query(self, text: str) -> list[float]:
        """
        توليد embedding لاستعلام بحث واحد.
        
        Args:
            text: نص البحث
        
        Returns:
            embedding (list[float] بطول 1024)
        """
        embeddings, tokens = self._embed_batch([text], input_type="query")
        
        # تحديث الإحصائيات
        self.total_tokens += tokens
        self.total_calls += 1
        cost = (tokens / 1_000_000) * self.PRICING_PER_1M_TOKENS.get(self.model, 0.06)
        self.total_cost += cost
        
        return embeddings[0]
    
    def get_stats(self) -> dict:
        """إرجاع إحصائيات الاستخدام."""
        return {
            "total_calls": self.total_calls,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost, 6),
            "model": self.model,
        }


# ---------- اختبار سريع ----------
if __name__ == "__main__":
    from stv_studio.config import settings
    
    print("[TEST] Voyage AI Embeddings")
    print(f"   Model: {settings.voyage_model}")
    print("=" * 60)
    
    embedder = VoyageEmbeddings(
        api_key=settings.voyage_api_key.get_secret_value(),
        model=settings.voyage_model,
    )
    
    # اختبار: 3 عناوين
    test_titles = [
        "احتجاجات في السويداء بعد قرارات حكومية جديدة",
        "افتتاح جسر جديد في مدينة حلب لتسهيل حركة المرور",
        "مفاوضات دبلوماسية بين سوريا وتركيا في أنقرة",
    ]
    
    print(f"\n[Embedding {len(test_titles)} test titles...]")
    embeddings = embedder.embed_documents(test_titles, show_progress=True)
    
    print(f"\n[Results]")
    for i, (title, emb) in enumerate(zip(test_titles, embeddings)):
        print(f"   Title {i+1}: {title[:50]}...")
        print(f"   Vector: length={len(emb)}, first 5 values={emb[:5]}")
        print()
    
    # اختبار: search query
    print("[Query Embedding]")
    query_vec = embedder.embed_query("مفاوضات دولية")
    print(f"   Query vector: length={len(query_vec)}, first 5={query_vec[:5]}")
    
    # الإحصائيات
    stats = embedder.get_stats()
    print(f"\n[Stats]")
    print(f"   Total calls: {stats['total_calls']}")
    print(f"   Total tokens: {stats['total_tokens']}")
    print(f"   Total cost: ${stats['total_cost_usd']:.6f}")