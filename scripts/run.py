"""
Run - نقطة الدخول التفاعلية
================================
تشغّل بأمر واحد، تلصق نص التقرير مباشرة بالـ Terminal، وخلص.
لا حاجة لإنشاء ملف .txt يدوياً.

الاستخدام:
    python scripts/run.py

    ثم الصق نص التقرير، واضغط Enter مرتين (سطر فاضي) لإنهاء الإدخال.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from process_report import process  # noqa: E402


def read_multiline_input() -> str:
    """
    يقرأ نص متعدد الأسطر من stdin حتى يجد سطرين فاضيين متتاليين،
    أو حتى Ctrl+D (EOF).
    """
    print("=" * 70)
    print("📝 الصق نص التقرير أدناه")
    print("   (اضغط Enter مرتين متتاليتين لإنهاء الإدخال، أو Ctrl+D)")
    print("=" * 70)
    print()

    lines = []
    empty_line_count = 0

    while True:
        try:
            line = input()
        except EOFError:
            break

        if line.strip() == "":
            empty_line_count += 1
            if empty_line_count >= 2 and lines:
                break
        else:
            empty_line_count = 0

        lines.append(line)

    text = "\n".join(lines).strip()
    return text


def main():
    transcript = read_multiline_input()

    if not transcript:
        print("\n❌ لم يتم إدخال أي نص. الخروج.")
        sys.exit(1)

    print(f"\n✅ تم استلام النص ({len(transcript)} حرف)")
    print()

    asyncio.run(process(transcript))


if __name__ == "__main__":
    main()
