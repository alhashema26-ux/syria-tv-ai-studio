"""
Title Generator Agent
======================
يأخذ AnalysisResult ويولّد 10 عناوين احترافية
باستخدام RAG (عناوين مشابهة) + Claude Sonnet 5.
"""

import json
import re
from typing import Optional

from pydantic import ValidationError

from stv_studio.config import PROJECT_ROOT
from stv_studio.memory.retriever import TitleRetriever
from stv_studio.providers.router import LLMRouter, TaskType
from stv_studio.schemas.analysis import AnalysisResult
from stv_studio.schemas.titles import TitleGenerationResult


class TitleAgent:
    """
    Agent يولّد عناوين YouTube احترافية.
    
    الاستخدام:
        agent = TitleAgent()
        result = await agent.generate(analysis_result)
        print(result.to_display())
    """
    
    PROMPT_PATH = PROJECT_ROOT / "src" / "stv_studio" / "prompts" / "title_generator.md"
    
    # عدد العناوين المرجعية من ChromaDB
    DEFAULT_K = 20
    
    def __init__(
        self,
        router: Optional[LLMRouter] = None,
        retriever: Optional[TitleRetriever] = None,
    ):
        self.router = router or LLMRouter()
        self.retriever = retriever or TitleRetriever()
        self.system_prompt = self._load_prompt()
    
    def _load_prompt(self) -> str:
        """قراءة الـ Prompt من ملف Markdown."""
        if not self.PROMPT_PATH.exists():
            raise FileNotFoundError(f"Prompt file not found: {self.PROMPT_PATH}")
        return self.PROMPT_PATH.read_text(encoding="utf-8")
    
    def _extract_json(self, text: str) -> str:
        """استخراج JSON من رد Claude."""
        text = text.strip()
        
        # JSON محاط بـ markdown code block
        code_block_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            text,
            re.DOTALL,
        )
        if code_block_match:
            return code_block_match.group(1)
        
        # JSON مباشر
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace : last_brace + 1]
        
        raise ValueError(f"No valid JSON found in response:\n{text[:500]}")
    
    def _build_user_prompt(
        self,
        analysis: AnalysisResult,
        reference_titles: list[dict],
    ) -> str:
        """بناء الرسالة الكاملة للـ user prompt."""
        
        # قسم 1: تحليل التقرير
        analysis_section = f"""## تحليل التقرير (AnalysisResult)

- **الموضوع:** {analysis.topic}
- **التصنيف:** {analysis.category}
- **النبرة:** {analysis.tone}
- **الشعور العام:** {analysis.emotion}
- **مستوى الأولوية:** {analysis.urgency_level or "غير محدد"}

### الملخص
{analysis.summary}

### الكيانات
- **أشخاص:** {", ".join(analysis.people) if analysis.people else "لا يوجد"}
- **منظمات:** {", ".join(analysis.organizations) if analysis.organizations else "لا يوجد"}
- **دول:** {", ".join(analysis.countries) if analysis.countries else "لا يوجد"}
- **أماكن:** {", ".join(analysis.locations) if analysis.locations else "لا يوجد"}

### التوجيه التحريري
- **زاوية YouTube:** {analysis.youtube_angle}
- **تركيز العنوان:** {analysis.title_focus}
- **الكلمات المفتاحية:** {", ".join(analysis.keywords[:10])}

### الاقتباسات المهمة
{chr(10).join(f'- "{q}"' for q in analysis.important_quotes) if analysis.important_quotes else "لا توجد اقتباسات مباشرة"}
"""
        
        # قسم 2: عناوين مرجعية
        reference_section = "## عناوين مرجعية (من الـ 49,819 عنوان)\n\n"
        reference_section += "**استلهم منها الأسلوب واللغة والزوايا، لكن لا تنسخها حرفياً:**\n\n"
        reference_section += self.retriever.format_for_prompt(
            reference_titles,
            include_channel=True,
            include_similarity=False,
        )
        
        # الرسالة الكاملة
        user_prompt = f"""{analysis_section}

{reference_section}

## المطلوب

بناءً على التحليل أعلاه والعناوين المرجعية:
- ولّد 10 عناوين احترافية متنوعة الأنماط
- اختر أقواها كتوصية
- أرجع JSON فقط بالشكل المحدد في System Prompt
"""
        
        return user_prompt
    
    async def generate(
        self,
        analysis: AnalysisResult,
        k: int = DEFAULT_K,
        context_block: str = "",
    ) -> TitleGenerationResult:
        """
        توليد 10 عناوين بناءً على AnalysisResult.
        
        Args:
            analysis: نتيجة TranscriptAnalyzer
            k: عدد العناوين المرجعية من RAG
        
        Returns:
            TitleGenerationResult: 10 عناوين + توصية
        """
        # الخطوة 1: البحث عن عناوين مشابهة
        reference_titles = self.retriever.find_by_analysis(
            topic=analysis.topic,
            keywords=analysis.keywords,
            title_focus=analysis.title_focus,
            k=k,
        )
        print(f"[RAG] Retrieved {len(reference_titles)} reference titles")
        # الخطوة 2: بناء الـ user prompt
        user_prompt = context_block + "\n\n" + self._build_user_prompt(analysis, reference_titles)
        
        # الخطوة 3: استدعاء Claude Sonnet 5 عبر Router
        response = await self.router.generate(
            prompt=user_prompt,
            task=TaskType.TITLE_GENERATION,
            system=self.system_prompt,
            max_tokens=10000,
        )
        
        # الخطوات 4-6: استخراج JSON مع retry حتى 3 محاولات
        last_error = None
        for attempt in range(3):
            try:
                if attempt > 0:
                    print(f"[TITLE] Retry attempt {attempt + 1}/3...")
                    response = await self.router.complete(
                        prompt=user_prompt,
                        task=TaskType.TITLE_GENERATION,
                        system=self.system_prompt,
                        max_tokens=10000,
                    )
                json_text = self._extract_json(response.text)
                data = json.loads(json_text)
                result = TitleGenerationResult(**data)
                return result
            except (ValueError, json.JSONDecodeError, ValidationError) as e:
                last_error = e
                print(f"[TITLE] Attempt {attempt + 1} failed: {e}")
                continue

        raise ValueError(f"Title generation failed after 3 attempts. Last error: {last_error}")


# ---------- اختبار سريع ----------
if __name__ == "__main__":
    import asyncio
    
    from stv_studio.agents.analyzer import TranscriptAnalyzer
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
    
    async def test():
        print("[TEST] Full Pipeline: Transcript -> Analysis -> Titles")
        print("=" * 70)
        
        # الخطوة 1: التحليل
        print("\n[1/3] Analyzing transcript...")
        analyzer = TranscriptAnalyzer()
        analysis = await analyzer.analyze(SAMPLE_TRANSCRIPT)
        print(f"[OK] Topic: {analysis.topic[:60]}...")
        
        # الخطوة 2: توليد العناوين
        print("\n[2/3] Generating 10 titles with RAG...")
        title_agent = TitleAgent(router=analyzer.router)
        titles_result = await title_agent.generate(analysis)
        print(f"[OK] Generated {len(titles_result.titles)} titles")
        
        # الخطوة 3: حفظ النتيجة في ملف Markdown
        print("\n[3/3] Saving report...")
        stats = analyzer.router.get_stats()
        
        saver = OutputSaver()
        filepath = saver.save_full_report(
            transcript=SAMPLE_TRANSCRIPT,
            analysis=analysis,
            titles=titles_result,
            cost_usd=stats["total_cost_usd"],
            input_tokens=stats["total_input_tokens"],
            output_tokens=stats["total_output_tokens"],
        )
        
        print(f"[OK] Saved to: {filepath}")
        print(f"\n{'=' * 70}")
        print(f"[COMPLETE] Total cost: ${stats['total_cost_usd']:.6f}")
        print(f"           Tokens: {stats['total_input_tokens']} in, {stats['total_output_tokens']} out")
        print(f"\n📄 Open the file in VS Code to view with proper RTL:")
        print(f"   {filepath}")
    
    asyncio.run(test())