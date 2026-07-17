"""
Process Report - السكريبت الرئيسي
====================================
يأخذ نص تقرير خام، ويشغّل السلسلة الكاملة مع حفظ تدريجي (Checkpointing):
Analyzer -> Title Generator -> Description Generator -> Thumbnail Generator
-> Quality Evaluator (GPT مستقل) -> حفظ التقرير النهائي.

كل خطوة تُحفظ فور نجاحها في outputs/checkpoints/، فلو فشلت خطوة لاحقة،
نتائج الخطوات الناجحة تبقى محفوظة ولا تُفقد.

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
from stv_studio.agents.thumbnail_generator import ThumbnailAgent
from stv_studio.agents.quality_evaluator import QualityEvaluator
from stv_studio.utils.output_saver import OutputSaver
from stv_studio.utils.checkpoint import CheckpointManager


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
    print("Syria TV AI Studio — Full Pipeline (with Checkpointing)")
    print("=" * 70)

    cp = CheckpointManager()
    analyzer = TranscriptAnalyzer()

    # الخطوة 1: التحليل
    try:
        print("\n[1/6] Analyzing transcript...")
        analysis = await analyzer.analyze(transcript)
        print(f"[OK] Topic: {analysis.topic[:70]}...")
        cp.save_step("analysis", analysis.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
    except Exception as e:
        cp.mark_failed("analysis", str(e))
        print(f"\n❌ FAILED at step 1 (Analysis): {e}")
        print(f"📄 Checkpoint saved: {cp.filepath}")
        raise

    # الخطوة 2: العناوين
    try:
        print("\n[2/6] Generating 10 titles with RAG...")
        title_agent = TitleAgent(router=analyzer.router)
        titles_result = await title_agent.generate(analysis)
        chosen_title = titles_result.titles[titles_result.recommended.index].text
        print(f"[OK] Chosen title: {chosen_title}")
        cp.save_step("titles", titles_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
    except Exception as e:
        cp.mark_failed("titles", str(e))
        print(f"\n❌ FAILED at step 2 (Titles): {e}")
        print(f"📄 Checkpoint saved (analysis is safe): {cp.filepath}")
        raise

    # الخطوة 3: الوصف
    try:
        print("\n[3/6] Generating description...")
        desc_agent = DescriptionAgent(router=analyzer.router)
        desc_result = await desc_agent.generate(analysis, chosen_title)
        print(f"[OK] Description generated ({len(desc_result.keywords)} keywords, {len(desc_result.hashtags)} hashtags)")
        cp.save_step("description", desc_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
    except Exception as e:
        cp.mark_failed("description", str(e))
        print(f"\n❌ FAILED at step 3 (Description): {e}")
        print(f"📄 Checkpoint saved (analysis + titles are safe): {cp.filepath}")
        raise

    # الخطوة 4: أفكار الثمبنيل
    try:
        print("\n[4/6] Generating thumbnail options...")
        thumb_agent = ThumbnailAgent(router=analyzer.router)
        thumb_result = await thumb_agent.generate(analysis, chosen_title)
        chosen_thumbnail = thumb_result.options[thumb_result.recommended_index]
        print(f"[OK] Generated {len(thumb_result.options)} thumbnail options")
        cp.save_step("thumbnail", thumb_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
    except Exception as e:
        cp.mark_failed("thumbnail", str(e))
        print(f"\n❌ FAILED at step 4 (Thumbnail): {e}")
        print(f"📄 Checkpoint saved (analysis + titles + description are safe): {cp.filepath}")
        raise

    # الخطوة 5: التقييم المستقل (GPT)
    try:
        print("\n[5/6] Evaluating quality (independent model)...")
        evaluator = QualityEvaluator(router=analyzer.router)
        eval_result = await evaluator.evaluate(
            transcript=transcript,
            analysis=analysis,
            chosen_title=chosen_title,
            description=desc_result.description,
            chosen_thumbnail=chosen_thumbnail,
        )
        print(f"[OK] Overall score: {eval_result.overall_score}/100 — {eval_result.verdict}")
        cp.save_step("evaluation", eval_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
    except Exception as e:
        cp.mark_failed("evaluation", str(e))
        print(f"\n❌ FAILED at step 5 (Evaluation): {e}")
        print(f"📄 Checkpoint saved (all content is safe, only evaluation missing): {cp.filepath}")
        raise

    # الخطوة 6: الحفظ النهائي
    print("\n[6/6] Saving full report...")
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

    with open(filepath, "a", encoding="utf-8") as f:
        f.write("\n---\n\n## 📄 الوصف والكلمات المفتاحية\n\n")
        f.write(f"### الوصف\n{desc_result.description}\n\n")
        f.write(f"### الكلمات المفتاحية ({len(desc_result.keywords)})\n")
        f.write(", ".join(desc_result.keywords) + "\n\n")
        f.write(f"### الهاشتاغات ({len(desc_result.hashtags)})\n")
        f.write(" ".join(desc_result.hashtags) + "\n")

        f.write("\n---\n\n## 🖼️ أفكار نص الثمبنيل\n\n")
        for i, opt in enumerate(thumb_result.options):
            marker = " ⭐" if i == thumb_result.recommended_index else ""
            f.write(f"**{i}. {opt.text}**{marker} ({opt.word_count} كلمات)\n")
            f.write(f"   - ملاحظة بصرية: {opt.visual_note}\n\n")

        f.write("\n---\n\n## 🔍 تقييم الجودة المستقل (GPT)\n\n")
        f.write(f"**التقييم الإجمالي:** {eval_result.overall_score}/100\n\n")
        f.write(f"**الحكم:** {eval_result.verdict}\n\n")
        f.write(f"**جاهز للنشر:** {'✅ نعم' if eval_result.ready_to_publish else '❌ لا'}\n\n")

        f.write("### المعايير التفصيلية\n\n")
        for c in eval_result.criteria:
            f.write(f"- **{c.name}:** {c.score}/100 — {c.comment}\n")

        f.write("\n### نقاط القوة\n\n")
        for s in eval_result.strengths:
            f.write(f"- {s}\n")

        if eval_result.weaknesses:
            f.write("\n### نقاط الضعف\n\n")
            for w in eval_result.weaknesses:
                f.write(f"- {w}\n")

    cp.mark_complete()
    print(f"[OK] Saved to: {filepath}")

    print(f"\n{'=' * 70}")
    print(f"[COMPLETE] Total cost: ${stats['total_cost_usd']:.6f}")
    print(f"           Tokens: {stats['total_input_tokens']} in, {stats['total_output_tokens']} out")
    print(f"           Quality: {eval_result.overall_score}/100 ({'✅ Ready' if eval_result.ready_to_publish else '❌ Needs review'})")
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
