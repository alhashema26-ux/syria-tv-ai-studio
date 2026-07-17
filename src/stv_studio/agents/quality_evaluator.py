"""
Quality Evaluator Agent
==========================
يراجع العنوان + الوصف + فكرة الثمبنيل المُختارين
بنموذج مستقل (GPT) عن النموذج المولّد (Claude)، ويعطي تقييماً موضوعياً.
"""

import json
import re
from typing import Optional

from pydantic import ValidationError

from stv_studio.config import PROJECT_ROOT
from stv_studio.providers.router import LLMRouter, TaskType
from stv_studio.schemas.analysis import AnalysisResult
from stv_studio.schemas.evaluation import EvaluationResult
from stv_studio.schemas.thumbnail import ThumbnailOption


class QualityEvaluator:
    """
    Agent يقيّم جودة المخرجات النهائية بنموذج مستقل.

    الاستخدام:
        evaluator = QualityEvaluator()
        result = await evaluator.evaluate(
            transcript, analysis, chosen_title, description, chosen_thumbnail
        )
        print(result.to_display())
    """

    PROMPT_PATH = PROJECT_ROOT / "src" / "stv_studio" / "prompts" / "quality_evaluator.md"

    def __init__(self, router: Optional[LLMRouter] = None):
        self.router = router or LLMRouter()
        self.system_prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        if not self.PROMPT_PATH.exists():
            raise FileNotFoundError(f"Prompt file not found: {self.PROMPT_PATH}")
        return self.PROMPT_PATH.read_text(encoding="utf-8")

    def _extract_json(self, text: str) -> str:
        text = text.strip()

        code_block_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            text,
            re.DOTALL,
        )
        if code_block_match:
            return code_block_match.group(1)

        first_brace = text.find("{")
        last_brace = text.rfind("}")

        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace : last_brace + 1]

        raise ValueError(f"No valid JSON found in response:\n{text[:500]}")

    def _build_user_prompt(
        self,
        transcript: str,
        analysis: AnalysisResult,
        chosen_title: str,
        description: str,
        chosen_thumbnail: Optional[ThumbnailOption] = None,
    ) -> str:
        return f"""## النص الأصلي

{transcript.strip()}

## التحليل (AnalysisResult)

- **الموضوع:** {analysis.topic}
- **التصنيف:** {analysis.category}
- **النبرة:** {analysis.tone}

## العنوان المُختار

{chosen_title}

## الوصف الكامل

{description}

## فكرة الثمبنيل المُوصى بها

- **النص:** {chosen_thumbnail.text if chosen_thumbnail else "لا يوجد (لم يُطلب توليد ثمبنيل)"}
- **البريف البصري:** {chosen_thumbnail.visual_note if chosen_thumbnail else "غير متاح"}

## المطلوب

راجع كل ما سبق بعين نقدية مستقلة وفق المعايير المحددة في System Prompt، وأرجع JSON فقط.
"""

    async def evaluate(
        self,
        transcript: str,
        analysis: AnalysisResult,
        chosen_title: str,
        description: str,
        chosen_thumbnail: Optional[ThumbnailOption] = None,
    ) -> EvaluationResult:
        user_prompt = self._build_user_prompt(
            transcript, analysis, chosen_title, description, chosen_thumbnail
        )

        response = await self.router.generate(
            prompt=user_prompt,
            task=TaskType.QUALITY_EVALUATION,
            system=self.system_prompt,
            max_tokens=3000,
        )

        try:
            json_text = self._extract_json(response.text)
        except ValueError as e:
            raise ValueError(
                f"Failed to extract JSON.\n"
                f"Provider: {response.provider}, Model: {response.model}\n"
                f"Raw response:\n{response.text[:1000]}\n\nError: {e}"
            )

        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON:\n{json_text[:1000]}\n\nError: {e}")

        try:
            result = EvaluationResult(**data)
        except ValidationError as e:
            raise ValueError(
                f"Schema validation failed.\n"
                f"Data: {json.dumps(data, ensure_ascii=False, indent=2)[:2000]}\n\n"
                f"Errors: {e}"
            )

        return result


# ---------- اختبار سريع ----------
if __name__ == "__main__":
    import asyncio

    from stv_studio.agents.analyzer import TranscriptAnalyzer
    from stv_studio.agents.title_generator import TitleAgent
    from stv_studio.agents.description_generator import DescriptionAgent
    from stv_studio.agents.thumbnail_generator import ThumbnailAgent

    SAMPLE_TRANSCRIPT = """
    شهدت مدينة الطبقة بريف الرقة وقفة احتجاجية طالب خلالها الاهالي باصلاحات ادارية شاملة،
    ومحاسبة المتورطين في قضايا فساد، وتحسين مستوى الخدمات العامة والواقع المعيشي.
    كما دعا المشاركون الى تمكين الكفاءات وابعاد اصحاب شبهات الفساد عن مواقع المسؤولية،
    مؤكدين اهمية تعزيز الشفافية والاستجابة لمطالب المواطنين.

    وقال احد المشاركين: نطالب باصلاح حقيقي وليس مجرد شعارات، فالوضع لم يعد يحتمل.
    واضاف مشارك اخر ان المدينة تعاني من نقص حاد في الخدمات الاساسية منذ سنوات،
    وان الحكومة السورية الجديدة يجب ان تتحرك بسرعة لمعالجة هذه المشاكل.
    """

    async def test():
        print("[TEST] Quality Evaluator")
        print("=" * 70)

        print("\n[1/5] Analyzing transcript...")
        analyzer = TranscriptAnalyzer()
        analysis = await analyzer.analyze(SAMPLE_TRANSCRIPT)
        print(f"[OK] Topic: {analysis.topic[:60]}...")

        print("\n[2/5] Generating title...")
        title_agent = TitleAgent(router=analyzer.router)
        titles_result = await title_agent.generate(analysis)
        chosen_title = titles_result.titles[titles_result.recommended.index].text
        print(f"[OK] Chosen title: {chosen_title}")

        print("\n[3/5] Generating description...")
        desc_agent = DescriptionAgent(router=analyzer.router)
        desc_result = await desc_agent.generate(analysis, chosen_title)
        print("[OK] Description generated")

        print("\n[4/5] Generating thumbnail...")
        thumb_agent = ThumbnailAgent(router=analyzer.router)
        thumb_result = await thumb_agent.generate(analysis, chosen_title)
        chosen_thumbnail = thumb_result.options[thumb_result.recommended_index]
        print(f"[OK] Chosen thumbnail: {chosen_thumbnail.text}")

        print("\n[5/5] Evaluating quality (independent model)...")
        evaluator = QualityEvaluator(router=analyzer.router)
        eval_result = await evaluator.evaluate(
            transcript=SAMPLE_TRANSCRIPT,
            analysis=analysis,
            chosen_title=chosen_title,
            description=desc_result.description,
            chosen_thumbnail=chosen_thumbnail,
        )
        print(eval_result.to_display())

        stats = analyzer.router.get_stats()
        print(f"\n[COMPLETE] Total cost: ${stats['total_cost_usd']:.6f}")
        print(f"           Tokens: {stats['total_input_tokens']} in, {stats['total_output_tokens']} out")

    asyncio.run(test())
