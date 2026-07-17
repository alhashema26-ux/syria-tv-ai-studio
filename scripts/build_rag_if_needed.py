"""
Build RAG If Needed - بناء تلقائي عند النشر
================================================
يتحقق من وجود ChromaDB جاهزة. إذا غير موجودة (أول نشر على Railway)،
يبني القاعدة تلقائياً: Excel -> JSONL -> ChromaDB.
يُستدعى قبل تشغيل السيرفر مباشرة.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
CHROMA_DIR = PROJECT_ROOT / "data" / "chroma_db"
JSONL_FILE = PROJECT_ROOT / "data" / "processed" / "all_titles_v1.jsonl"


def chroma_exists_and_populated() -> bool:
    """يتحقق إذا الـ ChromaDB موجودة وفيها بيانات فعلية (مش مجرد مجلد فارغ)."""
    if not CHROMA_DIR.exists():
        return False
    sqlite_file = CHROMA_DIR / "chroma.sqlite3"
    if not sqlite_file.exists():
        return False
    # لو حجمها أكبر من 1 ميجا، فيها بيانات فعلية
    return sqlite_file.stat().st_size > 1_000_000


def main():
    if chroma_exists_and_populated():
        print("[BUILD] ChromaDB already exists and populated. Skipping build.")
        return

    print("[BUILD] ChromaDB not found or empty. Building from scratch...")
    print("[BUILD] Step 1/2: Converting Excel files to JSONL...")

    result1 = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "convert_excel_to_jsonl.py")],
        cwd=str(PROJECT_ROOT),
    )
    if result1.returncode != 0:
        print("[BUILD] ❌ Failed at Excel -> JSONL conversion.")
        sys.exit(1)

    if not JSONL_FILE.exists():
        print(f"[BUILD] ❌ Expected output file not found: {JSONL_FILE}")
        sys.exit(1)

    print("[BUILD] Step 2/2: Ingesting titles into ChromaDB (this may take a few minutes)...")

    result2 = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "ingest_titles.py")],
        cwd=str(PROJECT_ROOT),
    )
    if result2.returncode != 0:
        print("[BUILD] ❌ Failed at ChromaDB ingestion.")
        sys.exit(1)

    print("[BUILD] ✅ RAG database built successfully.")


if __name__ == "__main__":
    main()
