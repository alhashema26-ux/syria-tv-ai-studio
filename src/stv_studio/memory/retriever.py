"""
Title Retriever - البحث الدلالي في قاعدة العناوين
====================================================
يستخدم Voyage AI + ChromaDB لإيجاد أقرب K عنوان
لأي استعلام أو تحليل نص.
"""

from typing import Optional

from stv_studio.config import settings
from stv_studio.embeddings.voyage import VoyageEmbeddings
from stv_studio.memory.vector_store import VectorStore


class TitleRetriever:
    """
    Retrieves similar titles from ChromaDB using Voyage embeddings.
    
    الاستخدام:
        retriever = TitleRetriever()
        results = retriever.find_similar(
            query="احتجاجات في السويداء",
            k=20
        )
    """
    
    def __init__(
        self,
        embedder: Optional[VoyageEmbeddings] = None,
        store: Optional[VectorStore] = None,
    ):
        """
        Args:
            embedder: Voyage embeddings instance (اختياري)
            store: Vector store instance (اختياري)
        """
        self.embedder = embedder or VoyageEmbeddings(
            api_key=settings.voyage_api_key.get_secret_value(),
            model=settings.voyage_model,
        )
        self.store = store or VectorStore()
    
    def find_similar(
        self,
        query: str,
        k: int = 20,
        channel_filter: Optional[str] = None,
        min_similarity: float = 0.0,
    ) -> list[dict]:
        """
        البحث عن أقرب K عنوان دلالياً.
        
        Args:
            query: نص البحث (تحليل، موضوع، عنوان مقترح)
            k: عدد النتائج المطلوبة
            channel_filter: تصفية بقناة (aljazeera, syriatv, ...)
            min_similarity: أقل similarity مقبول (تصفية النتائج الضعيفة)
        
        Returns:
            قائمة نتائج، كل واحدة dict:
                - title (str)
                - channel (str)
                - similarity_score (float)
                - url (str)
                - metadata (dict)
        """
        # توليد embedding للـ query
        query_vec = self.embedder.embed_query(query)
        
        # البحث في ChromaDB
        results = self.store.search(
            query_embedding=query_vec,
            k=k,
            channel_filter=channel_filter,
        )
        
        # تصفية النتائج الضعيفة
        if min_similarity > 0:
            results = [r for r in results if r["similarity_score"] >= min_similarity]
        
        return results
    
    def find_by_analysis(
        self,
        topic: str,
        keywords: list[str],
        title_focus: Optional[str] = None,
        k: int = 20,
    ) -> list[dict]:
        """
        بحث متقدّم باستخدام AnalysisResult.
        يبني query أفضل من عدة حقول.
        
        Args:
            topic: موضوع التقرير
            keywords: كلمات مفتاحية
            title_focus: الفكرة المحورية للعنوان
            k: عدد النتائج
        
        Returns:
            قائمة عناوين مشابهة
        """
        # بناء query غني من مصادر متعددة
        query_parts = [topic]
        
        if title_focus:
            query_parts.append(title_focus)
        
        if keywords:
            # أهم 5 كلمات مفتاحية
            query_parts.extend(keywords[:5])
        
        # دمج بمسافات
        query = " ".join(query_parts)
        
        return self.find_similar(query=query, k=k)
    
    def format_for_prompt(
        self,
        results: list[dict],
        include_channel: bool = True,
        include_similarity: bool = False,
    ) -> str:
        """
        تنسيق النتائج لإدراجها في Prompt لـ Claude.
        
        Args:
            results: نتائج find_similar
            include_channel: أضف اسم القناة
            include_similarity: أضف الـ score
        
        Returns:
            نص منسّق للـ Prompt
        """
        lines = []
        for i, r in enumerate(results, 1):
            parts = []
            
            if include_channel:
                parts.append(f"[{r['metadata'].get('channel_ar', r['channel'])}]")
            
            if include_similarity:
                parts.append(f"({r['similarity_score']:.2f})")
            
            parts.append(r["title"])
            
            lines.append(f"{i}. " + " ".join(parts))
        
        return "\n".join(lines)


# ---------- اختبار سريع ----------
if __name__ == "__main__":
    print("[TEST] Title Retriever")
    print("=" * 70)
    
    retriever = TitleRetriever()
    
    # اختبار 1: بحث مباشر
    query = "احتجاجات وقفة شعبية في مدينة سورية للمطالبة بالإصلاحات"
    print(f"\n[Query] {query}")
    print("-" * 70)
    
    results = retriever.find_similar(query, k=10)
    print(retriever.format_for_prompt(results, include_similarity=True))
    
    # اختبار 2: بحث ذكي بحقول AnalysisResult
    print("\n\n[Query 2] Advanced search using analysis fields")
    print("-" * 70)
    
    results2 = retriever.find_by_analysis(
        topic="افتتاح جسر جديد",
        keywords=["حلب", "بنية تحتية", "إعادة إعمار", "خدمات", "طرق"],
        title_focus="عودة الحياة عبر مشاريع البنية التحتية",
        k=10,
    )
    print(retriever.format_for_prompt(results2, include_similarity=True))
    
    # اختبار 3: تصفية بقناة Syria TV فقط
    print("\n\n[Query 3] Syria TV titles only")
    print("-" * 70)
    
    results3 = retriever.find_similar(
        query="أخبار الحكومة السورية الجديدة والإصلاحات",
        k=5,
        channel_filter="syriatv",
    )
    print(retriever.format_for_prompt(results3, include_similarity=True))
    
    # الإحصائيات
    voyage_stats = retriever.embedder.get_stats()
    print(f"\n[Stats]")
    print(f"  Total queries: {voyage_stats['total_calls']}")
    print(f"  Total cost: ${voyage_stats['total_cost_usd']:.6f}")