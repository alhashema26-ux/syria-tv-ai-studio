"""
Convert Excel Title Files to Unified JSONL
============================================
يقرأ 5 ملفات Excel من data/raw/
ويحوّلها لملف JSONL موحّد في data/processed/
مع التنظيف، Deduplication، وتقرير الإحصائيات.
"""

import json
import re
from pathlib import Path
from typing import Optional

import pandas as pd


# ==================== الإعدادات ====================

RAW_DIR = Path("data/raw")
OUTPUT_FILE = Path("data/processed/all_titles_v1.jsonl")

# خريطة الملفات: filename_pattern -> (channel_id, channel_ar)
CHANNEL_MAP = {
    "الجزيرة": ("aljazeera", "الجزيرة"),
    "العربية": ("alarabiya", "العربية"),
    "العربي": ("alaraby", "العربي"),
    "الحدث": ("alhadath", "الحدث"),
    "تلفزيون سوريا": ("syriatv", "تلفزيون سوريا"),
}


# ==================== دوال التنظيف ====================

def clean_title(title: str) -> str:
    """
    تنظيف عنوان:
    - إزالة المسافات الزائدة
    - إزالة newlines
    - إزالة الرموز الغريبة في البداية والنهاية
    """
    if not isinstance(title, str):
        return ""
    
    # إزالة newlines وtabs
    title = title.replace("\n", " ").replace("\t", " ").replace("\r", " ")
    
    # ضغط المسافات المتعددة إلى واحدة
    title = re.sub(r"\s+", " ", title)
    
    # إزالة المسافات في البداية والنهاية
    title = title.strip()
    
    return title


def detect_channel(filename: str) -> Optional[tuple[str, str]]:
    """اكتشاف القناة من اسم الملف."""
    for arabic_name, (channel_id, channel_ar) in CHANNEL_MAP.items():
        if arabic_name in filename:
            return channel_id, channel_ar
    return None


def is_valid_title(title: str) -> bool:
    """
    فحص أن العنوان صالح للاستخدام:
    - غير فارغ
    - على الأقل 10 حروف
    - على الأقل 3 كلمات
    """
    if not title:
        return False
    if len(title) < 10:
        return False
    if len(title.split()) < 3:
        return False
    return True


# ==================== المعالجة الرئيسية ====================

def process_file(filepath: Path) -> list[dict]:
    """قراءة ملف Excel واحد وإرجاع قائمة عناوين منظمة."""
    
    # اكتشاف القناة
    channel_info = detect_channel(filepath.name)
    if not channel_info:
        print(f"  [SKIP] Cannot detect channel from filename: {filepath.name}")
        return []
    
    channel_id, channel_ar = channel_info
    
    # قراءة الـ Excel
    try:
        df = pd.read_excel(filepath, engine="openpyxl")
    except Exception as e:
        print(f"  [ERROR] Failed to read {filepath.name}: {e}")
        return []
    
    # التحقق من الأعمدة المطلوبة
    # نتوقع: عمود A = رقم، عمود B = العنوان، عمود C = Video ID
    columns = df.columns.tolist()
    print(f"  Columns detected: {columns}")
    print(f"  Rows: {len(df)}")
    
    # افتراض: أول عمود (بعد #) هو العنوان، والذي بعده هو Video ID
    # نستخدم أسماء الأعمدة العربية أو الإنجليزية
    title_col = None
    video_id_col = None
    
    for col in columns:
        col_str = str(col).strip().lower()
        if "عنوان" in str(col) or "title" in col_str:
            title_col = col
        elif "video" in col_str or "id" in col_str:
            video_id_col = col
    
    if title_col is None:
        # افتراض: العمود الثاني هو العنوان
        title_col = columns[1] if len(columns) > 1 else columns[0]
    
    if video_id_col is None and len(columns) >= 3:
        video_id_col = columns[2]
    
    print(f"  Title column: '{title_col}'")
    print(f"  Video ID column: '{video_id_col}'")
    
    # استخراج العناوين
    titles = []
    skipped_invalid = 0
    
    for idx, row in df.iterrows():
        raw_title = row[title_col]
        cleaned = clean_title(str(raw_title))
        
        if not is_valid_title(cleaned):
            skipped_invalid += 1
            continue
        
        # Video ID (قد يكون فارغاً)
        video_id = ""
        if video_id_col is not None:
            vid_raw = row[video_id_col]
            if pd.notna(vid_raw):
                video_id = str(vid_raw).strip()
        
        # بناء الـ record
        record = {
            "id": f"{channel_id}_{idx + 1:05d}",
            "channel": channel_id,
            "channel_ar": channel_ar,
            "title": cleaned,
            "video_id": video_id,
            "url": f"https://youtube.com/watch?v={video_id}" if video_id else "",
            "title_length": len(cleaned),
            "word_count": len(cleaned.split()),
        }
        titles.append(record)
    
    print(f"  Valid titles: {len(titles)}")
    print(f"  Skipped invalid: {skipped_invalid}")
    
    return titles


def deduplicate(records: list[dict]) -> tuple[list[dict], int]:
    """
    إزالة العناوين المكررة.
    نعتبر عنوانين مكررين إذا: نفس النص + نفس القناة.
    """
    seen = set()
    unique = []
    duplicates_count = 0
    
    for record in records:
        # مفتاح فريد: قناة + عنوان (بعد normalize)
        key = f"{record['channel']}|{record['title']}"
        
        if key in seen:
            duplicates_count += 1
            continue
        
        seen.add(key)
        unique.append(record)
    
    return unique, duplicates_count


# ==================== التنفيذ ====================

def main():
    print("=" * 70)
    print("Excel to JSONL Converter - STV Studio")
    print("=" * 70)
    
    if not RAW_DIR.exists():
        print(f"[ERROR] Directory not found: {RAW_DIR}")
        return
    
    # تأكد من مجلد الـ output
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # اكتشاف كل ملفات Excel
    excel_files = sorted(RAW_DIR.glob("*.xlsx"))
    
    if not excel_files:
        print(f"[ERROR] No .xlsx files found in {RAW_DIR}")
        return
    
    print(f"\nFound {len(excel_files)} Excel files:")
    for f in excel_files:
        print(f"  - {f.name}")
    
    # معالجة كل ملف
    all_records = []
    per_channel_stats = {}
    
    for filepath in excel_files:
        print(f"\n[Processing] {filepath.name}")
        print("-" * 70)
        records = process_file(filepath)
        
        if records:
            channel_ar = records[0]["channel_ar"]
            per_channel_stats[channel_ar] = len(records)
            all_records.extend(records)
    
    print("\n" + "=" * 70)
    print(f"Total records before dedup: {len(all_records)}")
    
    # Deduplication
    unique_records, dup_count = deduplicate(all_records)
    
    print(f"Duplicates removed: {dup_count}")
    print(f"Final unique records: {len(unique_records)}")
    
    # الحفظ كـ JSONL
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        for record in unique_records:
            # ensure_ascii=False = يحفظ العربية كما هي
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    print(f"\n[Saved] {OUTPUT_FILE}")
    print(f"[Size] {OUTPUT_FILE.stat().st_size / 1024:.1f} KB")
    
    # تقرير نهائي
    print("\n" + "=" * 70)
    print("Final Statistics per Channel:")
    print("-" * 70)
    for channel, count in sorted(per_channel_stats.items(), key=lambda x: -x[1]):
        print(f"  {channel:20s}: {count:>6,} titles")
    print("-" * 70)
    print(f"  {'TOTAL (unique)':20s}: {len(unique_records):>6,} titles")
    print("=" * 70)
    
    # عيّنة من النتيجة
    print("\n[Sample records - first 3]")
    for record in unique_records[:3]:
        print(json.dumps(record, ensure_ascii=False, indent=2))
        print()


if __name__ == "__main__":
    main()