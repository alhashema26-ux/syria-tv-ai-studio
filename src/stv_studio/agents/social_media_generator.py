"""
Social Media Generator Agent
================================
يأخذ نص التقرير الأصلي (+ سياق اختياري من التحليل)، ويولّد
حزمة نشر كاملة لست منصات: فيسبوك، إنستغرام، إكس، تلغرام، واتساب، تيك توك.
"""

import json
import re
from typing import Optional

from pydantic import ValidationError

from stv_studio.config import PROJECT_ROOT
from stv_studio.providers.router import LLMRouter, TaskType
from stv_studio.schemas.analysis import AnalysisResult
from stv_studio.schemas.social_media import SocialMediaResult


class SocialMediaAgent:
    """
    Agent يولّد حزمة نشر متعددة المنصات من نص خبري خام.

    الاستخدام:
        agent = SocialMediaAgent()
        result = await agent.generate(transcript, analysis)
        print(result.to_display())
    """

    PROMPT_PATH = PROJECT_ROOT / "src" / "stv_studio" / "prompts" / "social_media_generator.md"

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

    def _normalize_news_type(self, data: dict) -> dict:
        """
        يطبّع قيمة news_type لأقرب قيمة من الست المحصورة،
        لأنه Claude أحياناً يستخدم تنسيق مختلف قليلاً لنفس المعنى
        (مثال: "تقرير / تحليل" بدل "تقرير-تحليل").
        """
        valid_values = [
            "عاجل",
            "تقرير-تحليل",
            "مداخلة-تصريح",
            "متابعة-تطور",
            "إنساني-قصة",
            "اقتصادي-أرقام",
        ]

        if "classification" not in data or "news_type" not in data["classification"]:
            return data

        raw = data["classification"]["news_type"].strip()

        if raw in valid_values:
            return data

        # تطبيع: إزالة المسافات حول الفواصل، توحيد / إلى -
        cleaned = raw.replace(" / ", "-").replace("/", "-").replace(" ", "")

        if cleaned in valid_values:
            data["classification"]["news_type"] = cleaned
            return data

        # مطابقة جزئية (احتياطي أخير) — لو الكلمة الأولى تطابق
        for valid in valid_values:
            first_part = valid.split("-")[0]
            if raw.startswith(first_part):
                data["classification"]["news_type"] = valid
                return data

        # لو ما لقينا تطابق، نسيبها كما هي — Pydantic رح يرفضها بوضوح
        return data

    def _build_user_prompt(
        self,
        transcript: str,
        analysis: Optional[AnalysisResult] = None,
    ) -> str:
        parts = [f"## النص الإخباري الأصلي\n\n{transcript.strip()}"]

        if analysis:
            parts.append(f"""
## سياق إضافي (من تحليل سابق، للاستئناس فقط)

- الموضوع: {analysis.topic}
- التصنيف: {analysis.category}
- النبرة: {analysis.tone}
- الأماكن: {", ".join(analysis.locations) if analysis.locations else "لا يوجد"}
""")

        return "\n".join(parts)

    async def generate(
        self,
        transcript: str,
        analysis: Optional[AnalysisResult] = None,
    ) -> SocialMediaResult:
        user_prompt = self._build_user_prompt(transcript, analysis)

        response = await self.router.generate(
            prompt=user_prompt,
            task=TaskType.SOCIAL_MEDIA_GENERATION,
            system=self.system_prompt,
            max_tokens=16000,
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

        data = self._normalize_news_type(data)

        try:
            result = SocialMediaResult(**data)
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
        print("[TEST] Social Media Generator")
        print("=" * 70)

        print("\n[1/2] Analyzing transcript (for context)...")
        analyzer = TranscriptAnalyzer()
        analysis = await analyzer.analyze(SAMPLE_TRANSCRIPT)
        print(f"[OK] Topic: {analysis.topic[:60]}...")

        print("\n[2/2] Generating social media package...")
        social_agent = SocialMediaAgent(router=analyzer.router)
        result = await social_agent.generate(SAMPLE_TRANSCRIPT, analysis)
        print(result.to_display())

        stats = analyzer.router.get_stats()
        print(f"\n[COMPLETE] Total cost: ${stats['total_cost_usd']:.6f}")
        print(f"           Tokens: {stats['total_input_tokens']} in, {stats['total_output_tokens']} out")

    asyncio.run(test())
