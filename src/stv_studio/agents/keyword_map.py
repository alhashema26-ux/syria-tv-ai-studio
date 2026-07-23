"""
وكيل خريطة الكلمات المفتاحية من يوتيوب
=======================================
يستخدم YouTube Suggest API (مجاني، بدون مفتاح) لبناء شجرة كلمات مفتاحية:
- المستوى الأول: 10 اقتراحات من موضوع التقرير
- المستوى الثاني: 3 اقتراحات فرعية لكل واحد من الـ10 = 30

يُغذّى بـ:
- topic (من التحليل)
- keywords (من DescriptionAgent)

ويولّد شجرة بصرية جاهزة للعرض.
"""

import asyncio
import json as _json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from typing import Optional

from pydantic import BaseModel, Field


# ==================== Schemas ====================

class KeywordBranch(BaseModel):
    """فرع في الشجرة — كلمة رئيسية + اقتراحاتها الفرعية."""
    keyword: str
    sub_suggestions: list[str] = Field(default_factory=list)


class KeywordMapResult(BaseModel):
    """النتيجة الكاملة لخريطة الكلمات المفتاحية."""
    seed_query: str = Field(..., description="الاستعلام الأصلي المستخدم")
    total_keywords: int = Field(0, description="مجموع الكلمات المكتشفة")
    root_suggestions: list[str] = Field(default_factory=list, description="اقتراحات المستوى الأول (10)")
    branches: list[KeywordBranch] = Field(default_factory=list, description="الفروع مع اقتراحاتها")
    recommended_top: list[str] = Field(default_factory=list, description="أعلى 5 كلمات موصى بها")


# ==================== Agent ====================

class KeywordMapAgent:
    """
    وكيل يبني خريطة كلمات مفتاحية من YouTube Suggest API.

    الاستخدام:
        agent = KeywordMapAgent()
        result = await agent.generate(topic="سوريا اقتصاد", keywords=["دولار", "تضخم"])
    """

    SUGGEST_URL = "https://suggestqueries.google.com/complete/search"

    def __init__(self):
        pass

    def _fetch_suggestions_sync(self, query: str) -> list[str]:
        """
        يجيب اقتراحات YouTube لاستعلام محدد (بلوكينج - يُستدعى داخل executor).
        Returns list of up to 10 suggestions.
        """
        try:
            params = {
                "client": "youtube",
                "ds": "yt",
                "q": query,
                "hl": "ar",
            }
            url = self.SUGGEST_URL + "?" + urlencode(params)
            req = Request(url, headers={"User-Agent": "SyriaTV-Studio/1.0"})

            with urlopen(req, timeout=10) as response:
                raw_bytes = response.read()
                # YouTube قد يرجع windows-1256 لبعض الردود العربية
                for enc in ("utf-8", "windows-1256", "cp1256", "iso-8859-6", "latin-1"):
                    try:
                        raw = raw_bytes.decode(enc)
                        # نتحقق - لو النص العربي فيه محارف صحيحة، نعتمد الترميز
                        if any("\u0600" <= c <= "\u06FF" for c in raw):
                            break
                    except (UnicodeDecodeError, LookupError):
                        continue
                else:
                    raw = raw_bytes.decode("utf-8", errors="replace")

            # YouTube ترجع response بشكل: window.google.ac.h([...])
            # نحن نحتاج الـ list داخلها
            start = raw.find("[")
            end = raw.rfind("]")
            if start == -1 or end == -1:
                return []

            data = _json.loads(raw[start:end+1])
            # data = [query_used, [[suggestion, ...], ...], ...]
            if len(data) < 2 or not isinstance(data[1], list):
                return []

            suggestions = []
            for item in data[1]:
                if isinstance(item, list) and len(item) > 0:
                    suggestions.append(item[0])
                elif isinstance(item, str):
                    suggestions.append(item)

            return suggestions[:10]
        except Exception as e:
            print(f"[KEYWORD_MAP] Error fetching '{query}': {e}")
            return []

    async def _fetch_suggestions(self, query: str) -> list[str]:
        """نسخة async - تستدعي البلوكينج داخل executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._fetch_suggestions_sync, query)

    async def generate(
        self,
        topic: str,
        keywords: Optional[list[str]] = None,
    ) -> KeywordMapResult:
        """
        يبني خريطة كلمات مفتاحية كاملة.

        Args:
            topic: موضوع التقرير الرئيسي
            keywords: كلمات مفتاحية إضافية من Description agent (اختياري)

        Returns:
            KeywordMapResult بشجرة مكونة من مستويين
        """
        # 1. نبني الاستعلام الأولي - نستخدم الموضوع فقط لضمان نتائج غنية
        # (keywords تُستخدم لاحقاً في تجميع النتائج، ليس في الاستعلام)
        # نستخدم keywords من DescriptionAgent إذا موجودة (أفضل جودة)
        # إلا نستخرج من الموضوع
        if keywords and len(keywords) >= 2:
            # نأخذ أول كلمة من كل keyword لأن الـ DescriptionAgent يولّد جمل طويلة
            short_kws = [kw.strip().split()[0] for kw in keywords if kw.strip()]
            seed_query = " ".join(short_kws[:2])
        else:
            stopwords = {"في", "من", "إلى", "على", "عن", "مع", "أن", "و", "أو", "لكن", "التي", "الذي", "هذا", "هذه", "ذلك", "تلك", "بعد", "قبل", "خلال", "لدى", "عند", "متوقعة", "متوقع", "القريب", "العاجل", "الآن", "اليوم", "أمس", "غداً", "للرئيس", "الرئيس"}
            words = topic.strip().split()
            meaningful = [w for w in words if w not in stopwords and len(w) > 1]
            seed_query = " ".join(meaningful[:2]) if meaningful else topic[:40]
        print(f"[KEYWORD_MAP] Seed query: {seed_query}")

        # 2. المستوى الأول - 10 اقتراحات
        root = await self._fetch_suggestions(seed_query)
        if not root:
            print("[KEYWORD_MAP] No root suggestions - returning empty result")
            return KeywordMapResult(
                seed_query=seed_query,
                total_keywords=0,
                root_suggestions=[],
                branches=[],
                recommended_top=[],
            )

        # 3. المستوى الثاني - 3 اقتراحات لكل واحد من الـ10
        branches = []
        # نعمل الاستعلامات بشكل متوازي
        tasks = [self._fetch_suggestions(sugg) for sugg in root[:10]]
        try:
            all_sub_results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            print(f"[KEYWORD_MAP] Gather error: {e}")
            all_sub_results = [[] for _ in root[:10]]

        for i, sugg in enumerate(root[:10]):
            sub = all_sub_results[i] if i < len(all_sub_results) else []
            if isinstance(sub, Exception):
                sub = []
            # نأخذ 3 فقط من كل فرع
            branch = KeywordBranch(
                keyword=sugg,
                sub_suggestions=sub[:3] if sub else [],
            )
            branches.append(branch)

        # 4. نحسب المجموع الكلي
        total = len(root) + sum(len(b.sub_suggestions) for b in branches)

        # 5. أعلى 5 كلمات موصى بها = أول 5 من root (YouTube يرتبهم حسب البحث)
        recommended = root[:5]

        return KeywordMapResult(
            seed_query=seed_query,
            total_keywords=total,
            root_suggestions=root,
            branches=branches,
            recommended_top=recommended,
        )
