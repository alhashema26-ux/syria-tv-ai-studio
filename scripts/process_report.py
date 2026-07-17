"""
Process Report - السكريبت الرئيسي
====================================
يأخذ نص تقرير خام، ويشغّل السلسلة الكاملة:
Analyzer -> Title Generator -> Description Generator -> حفظ التقرير.

الاستخدام:
    python scripts/process_report.py path/to/transcript.txt
    أو:
    python scripts/process_report.py   (يستخدم نص تجريبي مدمج)
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from stv_studio.agents.analyzer import TranscriptAnalyzer
from stv_studio.agents.title_generator import TitleAgent
from stv_studio.agents.description_generator import DescriptionAgent
from stv_studio.utils.output_saver import OutputSaver


SAMPLE_TRANSCRIPT = """
شهدت مدينة الطبقة بريف الرقة وقفة احتجاجية طالب خلالها الاهالي باصلاحات ادارية شاملة،
ومحاسبة المتورطين في قضايا فساد، وتحسين مستوى الخدمات العامة والواقع المعيشي.
كما دعا المشاركون الى تمكين الكفاءات وابعاد اصحاب شبهات الفساد عن مواقع المسؤولية،
مؤكدين اهمية تعزيز الشفافية والاستجابة لمطالب المواطنين.

وقال احد المشاركين: نطالب باصلاح حقيقي وليس مجرد شعارات، فالوضع لم يعد يحتمل.
واضاف مشارك اخر ان المدينة تعاني من نقص حاد في الخدمات الاساسية منذ سنوات،
وان الحكومة السورية الجديدة يجب ان تتحرك بسرعة لمعالجة هذه المشاكل.
"""


async def process(transcript: str):
    print("=" * 70)
    print("Syria TV AI Studio — Full Pipeline")
    print("=" * 70)

    # الخطوة 1: التحليل
    print("\n[1/4] Analyzing transcript...")
    analyzer = TranscriptAnalyzer()
    analysis = await analyzer.analyze(transcript)
    print(f"[OK] Topic: {analysis.topic[:70]}...")

    # الخطوة 2: العناوين (نفس الـ router عشان نجمع التكلفة)
    print("\n[2/4] Generating 10 titles with RAG...")
    title_agent = TitleAgent(router=analyzer.router)
    titles_result = await title_agent.generate(analysis)
    chosen_title = titles_result.titles[titles_result.recommended.index].text
    print(f"[OK] Chosen title: {chosen_title}")

    # الخطوة 3: الوصف
    print("\n[3/4] Generating description...")
    desc_agent = DescriptionAgent(router=analyzer.router)
    desc_result = await desc_agent.generate(analysis, chosen_title)
    print(f"[OK] Description generated ({len(desc_result.keywords)} keywords, {len(desc_result.hashtags)} hashtags)")

    # الخطوة 4: الحفظ
    print("\n[4/4] Saving full report...")
    stats = analyzer.router.get_stats()

    saver = OutputSaver()
    filepath = saver.save_full_report(
        transcript=transcript,
        analysis=analysis,
        titles=titles_result,
        cost_usd=stats["total_cost_usd"],
        input_tokens=stats["total_input_tokens"],
        output_tokens=stats["total_output_tokens"],
    )

    # نضيف الوصف يدوياً بآخر الملف (save_full_report ما بيعرف عنه)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write("\n---\n\n## 📄 الوصف والكلمات المفتاحية\n\n")
        f.write(f"### الوصف\n{desc_result.description}\n\n")
        f.write(f"### الكلمات المفتاحية ({len(desc_result.keywords)})\n")
        f.write(", ".join(desc_result.keywords) + "\n\n")
        f.write(f"### الهاشتاغات ({len(desc_result.hashtags)})\n")
        f.write(" ".join(desc_result.hashtags) + "\n")

    print(f"[OK] Saved to: {filepath}")

    print(f"\n{'=' * 70}")
    print(f"[COMPLETE] Total cost: ${stats['total_cost_usd']:.6f}")
    print(f"           Tokens: {stats['total_input_tokens']} in, {stats['total_output_tokens']} out")
    print(f"\n📄 Open in VS Code: {filepath}")

    return filepath


def main():
    if len(sys.argv) > 1:
        input_path = Path(sys.argv[1])
        if not input_path.exists():
            print(f"❌ File not found: {input_path}")
            sys.exit(1)
        transcript = input_path.read_text(encoding="utf-8")
        print(f"[INPUT] Loaded from: {input_path}")
    else:
        transcript = SAMPLE_TRANSCRIPT
        print("[INPUT] Using built-in sample transcript (no file argument given)")

    asyncio.run(process(transcript))


if __name__ == "__main__":
    main()
