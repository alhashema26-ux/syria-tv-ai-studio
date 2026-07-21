"""
Process Report V2 - نسخة منظّمة للواجهة الويب
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from stv_studio.agents.analyzer import TranscriptAnalyzer
from stv_studio.agents.title_generator import TitleAgent
from stv_studio.agents.description_generator import DescriptionAgent
from stv_studio.agents.thumbnail_generator import ThumbnailAgent
from stv_studio.agents.quality_evaluator import QualityEvaluator
from stv_studio.agents.social_media_generator import SocialMediaAgent
from stv_studio.agents.trend_context import TrendContextAgent
from stv_studio.utils.output_saver import OutputSaver
from stv_studio.utils.checkpoint import CheckpointManager


def _build_context_block(content_type, program_name):
    if not content_type and not program_name:
        return ""
    parts = ["\n## السياق التحريري\n"]
    if content_type:
        parts.append(f"- **نوع النص:** {content_type}")
    if program_name:
        parts.append(f"- **البرنامج:** {program_name}")
    parts.append("\nضع هذا السياق في الاعتبار عند توليد كل مخرجاتك.\n")
    return "\n".join(parts)


async def process_structured(
    transcript,
    content_type=None,
    program_name=None,
    include_titles=True,
    include_description=True,
    include_thumbnail=True,
    include_evaluation=True,
    include_social_media=False,
    include_trend_context=False,
    run_id=None,
):
    cp = CheckpointManager(run_id=run_id)
    cp._data["content_type"] = content_type
    cp._data["program_name"] = program_name
    cp._write()

    analyzer = TranscriptAnalyzer()
    context_block = _build_context_block(content_type, program_name)

    try:
        analysis = await analyzer.analyze(transcript, context_block=context_block)
        cp.save_step("analysis", analysis.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
    except Exception as e:
        cp.mark_failed("analysis", str(e))
        raise

    titles_result = None
    chosen_title = analysis.title_focus or analysis.topic[:70]

    if include_titles:
        try:
            title_agent = TitleAgent(router=analyzer.router)
            titles_result = await title_agent.generate(analysis, context_block=context_block)
            chosen_title = titles_result.titles[titles_result.recommended.index].text
            cp.save_step("titles", titles_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
        except Exception as e:
            cp.mark_failed("titles", str(e))
            raise

    desc_result = None

    if include_description:
        try:
            desc_agent = DescriptionAgent(router=analyzer.router)
            desc_result = await desc_agent.generate(analysis, chosen_title, context_block=context_block)
            cp.save_step("description", desc_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
        except Exception as e:
            cp.mark_failed("description", str(e))
            raise

    thumb_result = None
    chosen_thumbnail = None

    if include_thumbnail:
        try:
            thumb_agent = ThumbnailAgent(router=analyzer.router)
            thumb_result = await thumb_agent.generate(analysis, chosen_title, context_block=context_block)
            chosen_thumbnail = thumb_result.options[thumb_result.recommended_index]
            cp.save_step("thumbnail", thumb_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
        except Exception as e:
            cp.mark_failed("thumbnail", str(e))
            raise

    eval_result = None

    if include_evaluation:
        try:
            evaluator = QualityEvaluator(router=analyzer.router)
            eval_result = await evaluator.evaluate(
                transcript=transcript,
                analysis=analysis,
                chosen_title=chosen_title,
                description=desc_result.description if desc_result else "لا يوجد وصف",
                chosen_thumbnail=chosen_thumbnail,
            )
            cp.save_step("evaluation", eval_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
        except Exception as e:
            cp.mark_failed("evaluation", str(e))
            raise

    social_media_result = None

    if include_social_media:
        try:
            social_agent = SocialMediaAgent(router=analyzer.router)
            social_media_result = await social_agent.generate(transcript, analysis, context_block=context_block)
            cp.save_step("social_media", social_media_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
        except Exception as e:
            cp.mark_failed("social_media", str(e))
            raise

    # سياق الترند - جديد
    trend_context_result = None

    if include_trend_context:
        try:
            trend_agent = TrendContextAgent(router=analyzer.router)
            trend_context_result = await trend_agent.generate(analysis, context_block=context_block)
            cp.save_step("trend_context", trend_context_result.model_dump(), analyzer.router.get_stats()["total_cost_usd"])
        except Exception as e:
            cp.mark_failed("trend_context", str(e))
            # لا نرفع الخطأ - سياق الترند اختياري ولا يوقف باقي المعالجة
            print(f"[TREND] Error but continuing: {e}")

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

    cp.mark_complete()

    return {
        "cost": stats["total_cost_usd"],
        "content_type": content_type,
        "program_name": program_name,
        "analysis": analysis,
        "titles": titles_result,
        "description": desc_result,
        "thumbnail": thumb_result,
        "evaluation": eval_result,
        "social_media": social_media_result,
        "trend_context": trend_context_result,
        "raw_text": filepath.read_text(encoding="utf-8"),
        "filepath": str(filepath),
    }
