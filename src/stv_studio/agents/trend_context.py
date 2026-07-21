"""
وكيل سياق الترند - يبحث في Google Custom Search عن آخر 24 ساعة
ويستخدم Claude لتلخيص وتحليل النتائج تحريرياً.
"""
import os
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json as _json
from typing import Optional
from pydantic import BaseModel, Field

from stv_studio.providers.router import LLMRouter, TaskType
from stv_studio.schemas.analysis import AnalysisResult


# ==================== Schema للنتيجة ====================

class TrendSource(BaseModel):
    """مصدر واحد ظهر في نتائج البحث."""
    title: str
    link: str
    snippet: str
    source_name: Optional[str] = None
    published_time: Optional[str] = None


class TrendContextResult(BaseModel):
    """النتيجة الكاملة لسياق الترند."""
    query_used: str = Field(..., description="الاستعلام المُستخدم للبحث")
    total_results: int = Field(0, description="عدد النتائج الإجمالية")
    trend_status: str = Field(..., description="صاعد / مستقر / خامل / بدون بيانات")
    trend_status_emoji: str = Field(..., description="🔥 / 📊 / 💤 / ❓")
    editorial_summary: str = Field(..., description="ملخص تحريري ذكي")
    coverage_angles: list[str] = Field(default_factory=list, description="زوايا التغطية المختلفة")
    recommended_angle: str = Field(..., description="الزاوية المميزة المقترحة")
    top_sources: list[TrendSource] = Field(default_factory=list, description="أعلى 5 مصادر")
    hours_range: int = Field(24, description="الفترة الزمنية للبحث")


# ==================== الوكيل ====================

class TrendContextAgent:
    """
    وكيل يبحث في Google Custom Search ثم يستخدم Claude لتلخيص النتائج
    وتقديم رؤية تحريرية.
    """

    def __init__(self, router: LLMRouter):
        self.router = router
        self.google_api_key = os.environ.get("GOOGLE_SEARCH_API_KEY", "")
        self.google_engine_id = os.environ.get("GOOGLE_SEARCH_ENGINE_ID", "")

    async def _search_google(self, query: str, num_results: int = 10) -> list[dict]:
        """يبحث في Google Custom Search عن آخر 24 ساعة."""
        if not self.google_api_key or not self.google_engine_id:
            print("[TREND] Google Search credentials missing - skipping")
            return []

        params = {
            "key": self.google_api_key,
            "cx": self.google_engine_id,
            "q": query,
            "num": num_results,
            "dateRestrict": "d1",
            "lr": "lang_ar",
            "sort": "date",
        }
        url = "https://www.googleapis.com/customsearch/v1?" + urlencode(params)

        import asyncio
        loop = asyncio.get_event_loop()

        def _fetch():
            try:
                req = Request(url, headers={"User-Agent": "SyriaTV-Studio/1.0"})
                with urlopen(req, timeout=15) as response:
                    data = _json.loads(response.read().decode("utf-8"))
                    return data.get("items", [])
            except Exception as e:
                print(f"[TREND] Google Search error: {e}")
                return []

        return await loop.run_in_executor(None, _fetch)

    def _build_search_query(self, analysis: AnalysisResult) -> str:
        """يبني استعلام بحث ذكي من التحليل."""
        # نستخدم الموضوع + أهم كيان
        parts = [analysis.topic[:80]]

        # نضيف أهم كيان لو موجود
        if hasattr(analysis, "entities") and analysis.entities:
            top_entity = analysis.entities[0] if isinstance(analysis.entities, list) else None
            if top_entity and top_entity not in analysis.topic:
                parts.append(top_entity)

        return " ".join(parts)

    def _extract_source_name(self, url: str) -> str:
        """يستخرج اسم المصدر من الرابط."""
        try:
            from urllib.parse import urlparse
            hostname = urlparse(url).hostname or ""
            # نحذف www. ونأخذ الجزء الأول
            hostname = hostname.replace("www.", "")
            return hostname.split(".")[0].capitalize()
        except Exception:
            return "مصدر"

    async def generate(self, analysis: AnalysisResult, context_block: str = "") -> TrendContextResult:
        """
        يبحث في Google ويستخدم Claude لتحليل النتائج تحريرياً.
        """
        query = self._build_search_query(analysis)
        print(f"[TREND] Searching: {query}")

        # 1. البحث في Google
        raw_results = await self._search_google(query, num_results=10)

        # لو ما في نتائج، نرجّع نتيجة فاضية
        if not raw_results:
            return TrendContextResult(
                query_used=query,
                total_results=0,
                trend_status="بدون بيانات",
                trend_status_emoji="❓",
                editorial_summary="لم يتم العثور على تغطيات مطابقة للموضوع في آخر 24 ساعة. قد يكون الموضوع حديث جداً أو نادر التغطية.",
                coverage_angles=[],
                recommended_angle="ادرس الموضوع كخبر حصري أو زاوية جديدة غير مستهلكة",
                top_sources=[],
            )

        # 2. تجهيز المصادر للعرض
        top_sources = []
        for item in raw_results[:5]:
            source = TrendSource(
                title=item.get("title", ""),
                link=item.get("link", ""),
                snippet=item.get("snippet", ""),
                source_name=self._extract_source_name(item.get("link", "")),
            )
            top_sources.append(source)

        # 3. بناء prompt لـ Claude
        results_text = "\n\n".join([
            f"[{i+1}] المصدر: {src.source_name}\nالعنوان: {src.title}\nالمقتطف: {src.snippet}"
            for i, src in enumerate(top_sources)
        ])

        system_prompt = """أنت محلل تحريري خبير في تلفزيون سوريا. مهمتك تحليل نتائج البحث عن خبر معين وتقديم:
1. تقييم حالة الترند (صاعد / مستقر / خامل)
2. ملخص تحريري ذكي عن كيفية تغطية الموضوع
3. الزوايا المختلفة التي تناولها المنافسون
4. توصية بزاوية مميزة يمكن أن يتفرد بها تلفزيون سوريا

اللغة: العربية الفصحى.
الأسلوب: مهني، مباشر، تحليلي."""

        user_prompt = f"""{context_block}

الموضوع: {analysis.topic}
الاستعلام المُستخدم: {query}

نتائج البحث آخر 24 ساعة ({len(raw_results)} نتيجة):

{results_text}

قدّم تحليلك بصيغة JSON فقط، بدون أي نص إضافي:

{{
  "trend_status": "صاعد" أو "مستقر" أو "خامل",
  "trend_status_emoji": "🔥" أو "📊" أو "💤",
  "editorial_summary": "ملخص تحريري في 3-4 جمل عن كيف تناول المنافسون هذا الموضوع في آخر 24 ساعة، وما الملاحظات المهمة",
  "coverage_angles": ["الزاوية الأولى", "الزاوية الثانية", "الزاوية الثالثة"],
  "recommended_angle": "الزاوية المميزة التي أنصح تلفزيون سوريا بتبنّيها لتمييز محتواه عن المنافسين، في جملة أو جملتين"
}}"""

        # 4. استدعاء Claude
        try:
            response = await self.router.generate(
                prompt=user_prompt,
                task=TaskType.ANALYSIS,
                system=system_prompt,
                max_tokens=2000,
            )

            # استخراج JSON
            import json
            import re
            text = response.text

            # نبحث عن JSON
            json_match = re.search(r'\{[\s\S]*\}', text)
            if json_match:
                parsed = json.loads(json_match.group())
            else:
                raise ValueError("No JSON found in response")

            return TrendContextResult(
                query_used=query,
                total_results=len(raw_results),
                trend_status=parsed.get("trend_status", "مستقر"),
                trend_status_emoji=parsed.get("trend_status_emoji", "📊"),
                editorial_summary=parsed.get("editorial_summary", ""),
                coverage_angles=parsed.get("coverage_angles", []),
                recommended_angle=parsed.get("recommended_angle", ""),
                top_sources=top_sources,
            )

        except Exception as e:
            print(f"[TREND] Claude analysis error: {e}")
            # نرجّع نتيجة أساسية بدون تحليل Claude
            return TrendContextResult(
                query_used=query,
                total_results=len(raw_results),
                trend_status="مستقر",
                trend_status_emoji="📊",
                editorial_summary=f"تم العثور على {len(raw_results)} تغطية للموضوع في آخر 24 ساعة عبر {len(set(s.source_name for s in top_sources))} مصادر مختلفة.",
                coverage_angles=[],
                recommended_angle="راجع المصادر أدناه واختر زاوية غير مستهلكة",
                top_sources=top_sources,
            )
