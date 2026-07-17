"""
Process Report V2 - نسخة منظّمة للواجهة الويب
====================================================
نفس منطق process_report.py، لكن يرجع بيانات منظّمة (dict)
بدل مسار ملف نصي، لعرضها بصرياً بصفحة الويب.
"""

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


async def process_structured(
    transcript: str,
    include_titles: bool = True,
    include_description: bool = True,
    include_thumbnail: bool = True,
    include_evaluation: bool = True,
    run_id: str = None,
) -> dict:
    """
    يشغّل الـ Pipeline بخطوات مختارة، ويرجع dict منظّم بكل النتائج
    (objects حقيقية، جاهزة للعرض بـ Jinja2 مباشرة).
    """
    cp = CheckpointManager(run_id=run_id)
    analyzer = TranscriptAnalyzer()

    # الخطوة 1: التحليل (إلزامي دائماً)
    try:
        analysis = await analyzer.analyze(transcript)
        cp.save_step("analysis", analysis.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
    except Exception as e:
        cp.mark_failed("analysis", str(e))
        raise

    titles_result = None
    chosen_title = analysis.title_focus or analysis.topic[:70]

    # الخطوة 2: العناوين
    if include_titles:
        try:
            title_agent = TitleAgent(router=analyzer.router)
            titles_result = await title_agent.generate(analysis)
            chosen_title = titles_result.titles[titles_result.recommended.index].text
            cp.save_step("titles", titles_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
        except Exception as e:
            cp.mark_failed("titles", str(e))
            raise

    desc_result = None

    # الخطوة 3: الوصف
    if include_description:
        try:
            desc_agent = DescriptionAgent(router=analyzer.router)
            desc_result = await desc_agent.generate(analysis, chosen_title)
            cp.save_step("description", desc_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
        except Exception as e:
            cp.mark_failed("description", str(e))
            raise

    thumb_result = None
    chosen_thumbnail = None

    # الخطوة 4: الثمبنيل
    if include_thumbnail:
        try:
            thumb_agent = ThumbnailAgent(router=analyzer.router)
            thumb_result = await thumb_agent.generate(analysis, chosen_title)
            chosen_thumbnail = thumb_result.options[thumb_result.recommended_index]
            cp.save_step("thumbnail", thumb_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
        except Exception as e:
            cp.mark_failed("thumbnail", str(e))
            raise

    eval_result = None

    # الخطوة 5: التقييم المستقل
    if include_evaluation:
        try:
            evaluator = QualityEvaluator(router=analyzer.router)
            eval_result = await evaluator.evaluate(
                transcript=transcript,
                analysis=analysis,
                chosen_title=chosen_title,
                description=desc_result.description if desc_result else "لا يوجد وصف (لم يُطلب)",
                chosen_thumbnail=chosen_thumbnail,
            )
            cp.save_step("evaluation", eval_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
        except Exception as e:
            cp.mark_failed("evaluation", str(e))
            raise

    # حفظ نسخة Markdown أرشيفية أيضاً (بدون ما نعتمد عليها للعرض)
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

    if desc_result or thumb_result or eval_result:
        with open(filepath, "a", encoding="utf-8") as f:
            if desc_result:
                f.write("\n---\n\n## 📄 الوصف والكلمات المفتاحية\n\n")
                f.write(f"### الوصف\n{desc_result.description}\n\n")
                f.write(f"### الكلمات المفتاحية ({len(desc_result.keywords)})\n")
                f.write(", ".join(desc_result.keywords) + "\n\n")
                f.write(f"### الهاشتاغات ({len(desc_result.hashtags)})\n")
                f.write(" ".join(desc_result.hashtags) + "\n")
            if thumb_result:
                f.write("\n---\n\n## 🖼️ أفكار نص الثمبنيل\n\n")
                for i, opt in enumerate(thumb_result.options):
                    marker = " ⭐" if i == thumb_result.recommended_index else ""
                    f.write(f"**{i}. {opt.text}**{marker} ({opt.word_count} كلمات)\n")
                    f.write(f"   - ملاحظة بصرية: {opt.visual_note}\n\n")
            if eval_result:
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

    return {
        "cost": stats["total_cost_usd"],
        "analysis": analysis,
        "titles": titles_result,
        "description": desc_result,
        "thumbnail": thumb_result,
        "evaluation": eval_result,
        "raw_text": filepath.read_text(encoding="utf-8"),
        "filepath": str(filepath),
    }
