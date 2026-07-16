"""
Ingest Titles to ChromaDB
==========================
يقرأ data/processed/all_titles_v1.jsonl
يولّد embeddings عبر Voyage AI
يخزّنهم في ChromaDB
"""

import json
import time
from pathlib import Path

from stv_studio.config import settings
from stv_studio.embeddings.voyage import VoyageEmbeddings
from stv_studio.memory.vector_store import VectorStore


# ==================== الإعدادات ====================

INPUT_FILE = Path("data/processed/all_titles_v1.jsonl")
BATCH_SIZE = 128  # حجم دفعة Voyage AI
FLUSH_EVERY = 1000  # كم عنوان قبل ما نحفظ في ChromaDB

# لأمان الاختبار الأول: إذا FALSE، نعمل ingestion لكل الـ 49K
# إذا TRUE، بس أول 500 عنوان (للاختبار السريع بدون تكلفة)
DRY_RUN = False
DRY_RUN_LIMIT = 500


# ==================== دوال المعالجة ====================

def load_titles(filepath: Path) -> list[dict]:
    """قراءة JSONL كامل."""
    records = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def prepare_metadata(record: dict) -> dict:
    """
    استخراج metadata من record للـ ChromaDB.
    ChromaDB يقبل فقط: str, int, float, bool
    """
    return {
        "channel": record.get("channel", ""),
        "channel_ar": record.get("channel_ar", ""),
        "url": record.get("url", ""),
        "video_id": record.get("video_id", ""),
        "title_length": record.get("title_length", 0),
        "word_count": record.get("word_count", 0),
    }


# ==================== التنفيذ الرئيسي ====================

def main():
    print("=" * 70)
    print("Ingest Titles to ChromaDB")
    print("=" * 70)
    
    # 1. التحقق من الملف
    if not INPUT_FILE.exists():
        print(f"[ERROR] Input file not found: {INPUT_FILE}")
        return
    
    # 2. قراءة الـ titles
    print(f"\n[1/4] Loading titles from {INPUT_FILE}...")
    records = load_titles(INPUT_FILE)
    print(f"[OK] Loaded {len(records):,} titles")
    
    # 3. إذا DRY_RUN، اقتصر على أول N
    if DRY_RUN:
        print(f"\n[DRY RUN] Limiting to first {DRY_RUN_LIMIT} titles")
        records = records[:DRY_RUN_LIMIT]
    
    # 4. تهيئة Voyage AI
    print(f"\n[2/4] Initializing Voyage AI ({settings.voyage_model})...")
    embedder = VoyageEmbeddings(
        api_key=settings.voyage_api_key.get_secret_value(),
        model=settings.voyage_model,
    )
    print(f"[OK] Voyage AI ready")
    
    # 5. تهيئة ChromaDB
    print(f"\n[3/4] Initializing ChromaDB...")
    store = VectorStore()
    existing_count = store.count()
    print(f"[OK] ChromaDB ready. Current count: {existing_count:,}")
    
    # تحذير إذا في بيانات موجودة
    if existing_count > 0:
        print(f"\n[WARNING] ChromaDB already contains {existing_count:,} titles.")
        response = input("Do you want to (r)eset and re-ingest, (s)kip and add new only, or (c)ancel? [r/s/c]: ").lower().strip()
        
        if response == "c":
            print("Cancelled by user.")
            return
        elif response == "r":
            print("[RESET] Clearing existing data...")
            store.reset()
        elif response == "s":
            # نتحقق من الـ IDs الموجودة ونتخطاها
            print("[SKIP MODE] Not fully implemented - please choose reset for now")
            return
        else:
            print("Invalid choice. Cancelled.")
            return
    
    # 6. Ingestion
    print(f"\n[4/4] Ingesting {len(records):,} titles...")
    print(f"      Batch size: {BATCH_SIZE}")
    print(f"      Flush to DB every: {FLUSH_EVERY} titles")
    print("-" * 70)
    
    start_time = time.perf_counter()
    total_ingested = 0
    
    # نجمع في buffers قبل الحفظ في ChromaDB
    pending_embeddings = []
    pending_titles = []
    pending_metadatas = []
    pending_ids = []
    
    # نمر على الـ records في دفعات Voyage
    for batch_start in range(0, len(records), BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, len(records))
        batch_records = records[batch_start:batch_end]
        
        # استخراج النصوص
        batch_texts = [r["title"] for r in batch_records]
        
        # توليد embeddings (Voyage batch call)
        print(f"  [Voyage] Batch {batch_start//BATCH_SIZE + 1}/{(len(records) + BATCH_SIZE - 1)//BATCH_SIZE} - Embedding {len(batch_texts)} texts...", end=" ", flush=True)
        batch_start_time = time.perf_counter()
        
        embeddings, tokens = embedder._embed_batch(batch_texts, input_type="document")
        
        batch_time = time.perf_counter() - batch_start_time
        cost = (tokens / 1_000_000) * 0.06
        embedder.total_tokens += tokens
        embedder.total_calls += 1
        embedder.total_cost += cost
        
        print(f"{tokens} tokens, {batch_time:.1f}s, ${cost:.6f}")
        
        # إضافة للـ pending buffers
        for record, embedding in zip(batch_records, embeddings):
            pending_embeddings.append(embedding)
            pending_titles.append(record["title"])
            pending_metadatas.append(prepare_metadata(record))
            pending_ids.append(record["id"])
        
        # حفظ في ChromaDB كل FLUSH_EVERY
        if len(pending_embeddings) >= FLUSH_EVERY or batch_end >= len(records):
            print(f"  [ChromaDB] Flushing {len(pending_embeddings)} to DB...", end=" ", flush=True)
            flush_start = time.perf_counter()
            
            added = store.add_titles(
                embeddings=pending_embeddings,
                titles=pending_titles,
                metadatas=pending_metadatas,
                ids=pending_ids,
            )
            
            total_ingested += added
            flush_time = time.perf_counter() - flush_start
            print(f"OK ({flush_time:.1f}s). Total in DB: {total_ingested:,}")
            
            # امسح البuffers
            pending_embeddings = []
            pending_titles = []
            pending_metadatas = []
            pending_ids = []
    
    elapsed_total = time.perf_counter() - start_time
    
    # 7. التقرير النهائي
    print("\n" + "=" * 70)
    print("[COMPLETE]")
    print("-" * 70)
    print(f"Titles ingested: {total_ingested:,}")
    print(f"Total time: {elapsed_total:.1f}s ({elapsed_total/60:.1f} minutes)")
    print(f"Rate: {total_ingested/elapsed_total:.1f} titles/sec")
    
    print(f"\n[Voyage AI Stats]")
    voyage_stats = embedder.get_stats()
    print(f"  Total API calls: {voyage_stats['total_calls']}")
    print(f"  Total tokens: {voyage_stats['total_tokens']:,}")
    print(f"  Total cost: ${voyage_stats['total_cost_usd']:.4f}")
    
    print(f"\n[ChromaDB Stats]")
    db_stats = store.get_stats()
    print(f"  Total titles: {db_stats['total_titles']:,}")
    print(f"  Storage path: {db_stats['db_path']}")
    print(f"  Channels distribution:")
    for channel, count in sorted(db_stats['channels_sample'].items(), key=lambda x: -x[1]):
        print(f"    {channel}: {count:,}")
    
    print("\n" + "=" * 70)
    print("[SUCCESS] Ready for RAG queries!")
    print("=" * 70)


if __name__ == "__main__":
    main()