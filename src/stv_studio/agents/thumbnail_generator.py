"""
Thumbnail Generator Agent
============================
يأخذ AnalysisResult + العنوان المُختار، ويولّد
10 أفكار نصية قصيرة لثمبنيل بأسلوب إخباري جاد (4-6 كلمات لكل فكرة).
"""

import json
import re
from typing import Optional

from pydantic import ValidationError

from stv_studio.config import PROJECT_ROOT
from stv_studio.providers.router import LLMRouter, TaskType
from stv_studio.schemas.analysis import AnalysisResult
from stv_studio.schemas.thumbnail import ThumbnailResult


class ThumbnailAgent:
    """
    Agent يولّد أفكار نص الثمبنيل بأسلوب إخباري جاد.

    الاستخدام:
        agent = ThumbnailAgent()
        result = await agent.generate(analysis_result, chosen_title)
        print(result.to_display())
    """

    PROMPT_PATH = PROJECT_ROOT / "src" / "stv_studio" / "prompts" / "thumbnail_generator.md"

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
        analysis: AnalysisResult,
        chosen_title: str,
    ) -> str:
        analysis_section = f"""## تحليل التقرير (AnalysisResult)

- **الموضوع:** {analysis.topic}
- **التصنيف:** {analysis.category}
- **النبرة:** {analysis.tone}
- **الشعور العام:** {analysis.emotion}

### الأماكن
{", ".join(analysis.locations) if analysis.locations else "لا يوجد"}

### الكلمات المفتاحية
{", ".join(analysis.keywords[:10])}
"""

        title_section = f"""## العنوان المُختار (chosen_title)

"{chosen_title}"

⚠️ تذكير: أي كلمة وردت حرفياً بالعنوان أعلاه **ممنوع** استخدامها بنص أي ثمبنيل.
"""

        user_prompt = f"""{analysis_section}

{title_section}

## المطلوب

بناءً على التحليل والعنوان أعلاه:
- ولّد 10 أفكار نصية (4-6 كلمات لكل واحدة)، بأسلوب إخباري جاد
- التزم بقاعدة عدم تكرار كلمات العنوان
- اختر أقواها كتوصية
- أرجع JSON فقط بالشكل المحدد في System Prompt
"""

        return user_prompt

    async def generate(
        self,
        analysis: AnalysisResult,
        chosen_title: str,
        context_block: str = "",
    ) -> ThumbnailResult:
        user_prompt = context_block + "

" + self._build_user_prompt(analysis, chosen_title)

        response = await self.router.generate(
            prompt=user_prompt,
            task=TaskType.THUMBNAIL_TEXT,
            system=self.system_prompt,
            max_tokens=6000,
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
            result = ThumbnailResult(**data)
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
        print("[TEST] Thumbnail Generator (simplified)")
        print("=" * 70)

        print("\n[1/3] Analyzing transcript...")
        analyzer = TranscriptAnalyzer()
        analysis = await analyzer.analyze(SAMPLE_TRANSCRIPT)
        print(f"[OK] Topic: {analysis.topic[:60]}...")

        print("\n[2/3] Generating title (for context)...")
        title_agent = TitleAgent(router=analyzer.router)
        titles_result = await title_agent.generate(analysis)
        chosen_title = titles_result.titles[titles_result.recommended.index].text
        print(f"[OK] Chosen title: {chosen_title}")

        print("\n[3/3] Generating thumbnail options...")
        thumb_agent = ThumbnailAgent(router=analyzer.router)
        thumb_result = await thumb_agent.generate(analysis, chosen_title)
        print(thumb_result.to_display())

        stats = analyzer.router.get_stats()
        print(f"\n[COMPLETE] Total cost: ${stats['total_cost_usd']:.6f}")
        print(f"           Tokens: {stats['total_input_tokens']} in, {stats['total_output_tokens']} out")

    asyncio.run(test())
