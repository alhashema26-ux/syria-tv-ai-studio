"""
Vector Store - قاعدة بيانات ChromaDB للبحث الدلالي
====================================================
يدير التخزين، البحث، والحذف للـ embeddings.
"""

from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from stv_studio.config import PROJECT_ROOT


class VectorStore:
    """
    غلاف على ChromaDB مصمّم للـ RAG على عناوين الأخبار.
    
    الاستخدام:
        store = VectorStore()
        store.add_titles(embeddings, metadatas, ids)
        results = store.search(query_embedding, k=20)
    """
    
    # المسار الافتراضي للـ DB
    DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "chroma_db"
    
    # اسم الـ Collection الرئيسي
    DEFAULT_COLLECTION = "news_titles"
    
    def __init__(
        self,
        db_path: Optional[Path] = None,
        collection_name: str = DEFAULT_COLLECTION,
    ):
        """
        Args:
            db_path: مسار قاعدة البيانات (يُنشأ إذا لم يوجد)
            collection_name: اسم الـ collection
        """
        self.db_path = Path(db_path) if db_path else self.DEFAULT_DB_PATH
        self.db_path.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        
        # ChromaDB Client - Persistent (يحفظ على القرص)
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(
                anonymized_telemetry=False,  # لا نرسل بيانات لـ ChromaDB
                allow_reset=True,             # يسمح بحذف الـ DB عند الحاجة
            ),
        )
        
        # Collection - ننشئها إذا مش موجودة
        # ملاحظة: metadata={"hnsw:space": "cosine"} = نستخدم Cosine Similarity
        # (الأفضل للنصوص، بدل L2 الافتراضي)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    
    def add_titles(
        self,
        embeddings: list[list[float]],
        titles: list[str],
        metadatas: list[dict],
        ids: list[str],
    ) -> int:
        """
        إضافة عناوين مع embeddings إلى القاعدة.
        
        Args:
            embeddings: قائمة vectors (كل واحد بطول 1024)
            titles: قائمة نصوص العناوين
            metadatas: قائمة metadata لكل عنوان (channel, url, ...)
            ids: قائمة IDs فريدة
        
        Returns:
            عدد العناوين المُضافة
        """
        if not (len(embeddings) == len(titles) == len(metadatas) == len(ids)):
            raise ValueError(
                f"Mismatched lengths: embeddings={len(embeddings)}, "
                f"titles={len(titles)}, metadatas={len(metadatas)}, ids={len(ids)}"
            )
        
        if not embeddings:
            return 0
        
        # ChromaDB يقبل حتى ~5000 في batch واحد
        # نقسّم لدفعات صغيرة للسلامة
        batch_size = 1000
        total_added = 0
        
        for i in range(0, len(embeddings), batch_size):
            end = min(i + batch_size, len(embeddings))
            self.collection.add(
                embeddings=embeddings[i:end],
                documents=titles[i:end],
                metadatas=metadatas[i:end],
                ids=ids[i:end],
            )
            total_added += end - i
        
        return total_added
    
    def search(
        self,
        query_embedding: list[float],
        k: int = 20,
        channel_filter: Optional[str] = None,
    ) -> list[dict]:
        """
        بحث دلالي: إيجاد أقرب k عنوان للـ query.
        
        Args:
            query_embedding: vector الاستعلام
            k: عدد النتائج المطلوبة
            channel_filter: تصفية بقناة محددة (اختياري)
        
        Returns:
            قائمة نتائج، كل واحدة dict فيها:
                - title
                - channel
                - url
                - similarity_score (كلما أقرب لـ 1.0 = أشبه)
                - metadata
        """
        # بناء الـ filter
        where_clause = None
        if channel_filter:
            where_clause = {"channel": channel_filter}
        
        # البحث
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_clause,
        )
        
        # ChromaDB يرجع lists متداخلة - نفلّطها
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                # distance من ChromaDB = 1 - cosine_similarity
                # فنحوّلها لـ similarity score (أقرب لـ 1 = أشبه)
                distance = results["distances"][0][i]
                similarity = 1.0 - distance
                
                formatted.append({
                    "id": results["ids"][0][i],
                    "title": results["documents"][0][i],
                    "similarity_score": round(similarity, 4),
                    "metadata": results["metadatas"][0][i],
                    "channel": results["metadatas"][0][i].get("channel", ""),
                    "url": results["metadatas"][0][i].get("url", ""),
                })
        
        return formatted
    
    def count(self) -> int:
        """عدد العناوين في القاعدة."""
        return self.collection.count()
    
    def get_stats(self) -> dict:
        """إحصائيات الـ Collection."""
        total = self.count()
        
        # عدّ حسب القناة (نأخذ عيّنة)
        if total > 0:
            sample = self.collection.get(limit=min(total, 5000), include=["metadatas"])
            channels = {}
            for meta in sample["metadatas"]:
                ch = meta.get("channel", "unknown")
                channels[ch] = channels.get(ch, 0) + 1
        else:
            channels = {}
        
        return {
            "total_titles": total,
            "collection_name": self.collection_name,
            "db_path": str(self.db_path),
            "channels_sample": channels,
        }
    
    def reset(self):
        """حذف كل البيانات (استخدم بحذر!)."""
        self.client.delete_collection(name=self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )


# ---------- اختبار سريع ----------
if __name__ == "__main__":
    print("[TEST] Vector Store (ChromaDB)")
    print("=" * 60)
    
    # إنشاء store
    store = VectorStore()
    
    print(f"[OK] ChromaDB initialized at: {store.db_path}")
    print(f"[OK] Collection: {store.collection_name}")
    print(f"[OK] Current count: {store.count()}")
    
    # اختبار: إضافة 3 عناوين وهمية
    if store.count() == 0:
        print("\n[TEST] Adding 3 dummy titles...")
        
        # embeddings وهمية (عادةً من Voyage)
        dummy_embeddings = [
            [0.1] * 1024,
            [0.2] * 1024,
            [0.3] * 1024,
        ]
        
        dummy_titles = [
            "عنوان اختبار 1",
            "عنوان اختبار 2",
            "عنوان اختبار 3",
        ]
        
        dummy_metadatas = [
            {"channel": "test", "url": "https://example.com/1"},
            {"channel": "test", "url": "https://example.com/2"},
            {"channel": "test", "url": "https://example.com/3"},
        ]
        
        dummy_ids = ["test_001", "test_002", "test_003"]
        
        added = store.add_titles(
            embeddings=dummy_embeddings,
            titles=dummy_titles,
            metadatas=dummy_metadatas,
            ids=dummy_ids,
        )
        
        print(f"[OK] Added {added} test titles")
        
        # اختبار البحث
        print("\n[TEST] Searching for closest to [0.15]*1024...")
        results = store.search(
            query_embedding=[0.15] * 1024,
            k=3,
        )
        
        for i, r in enumerate(results):
            print(f"   #{i+1}: {r['title']} (similarity: {r['similarity_score']})")
        
        # تنظيف الاختبار
        print("\n[Cleanup] Resetting test data...")
        store.reset()
        print(f"[OK] Count after reset: {store.count()}")
    else:
        print(f"\n[INFO] Collection already has {store.count()} titles")
        print("[INFO] Skipping test to avoid contaminating real data")
    
    # إحصائيات نهائية
    print("\n[Stats]")
    stats = store.get_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")