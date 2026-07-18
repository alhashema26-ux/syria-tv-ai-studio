"""
Transcript Analyzer Agent
==========================
أول Agent حقيقي في النظام.
يأخذ نص transcript ويرجع AnalysisResult منظم.
"""

import json
import re
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from stv_studio.config import PROJECT_ROOT
from stv_studio.providers.router import LLMRouter, TaskType
from stv_studio.schemas.analysis import AnalysisResult


class TranscriptAnalyzer:
    """
    Agent يحلل النصوص الإخبارية ويستخرج البيانات المنظمة.
    
    الاستخدام:
        analyzer = TranscriptAnalyzer(router)
        result = await analyzer.analyze(transcript_text)
        print(result.topic)
    """
    
    # مسار ملف الـ Prompt
    PROMPT_PATH = PROJECT_ROOT / "src" / "stv_studio" / "prompts" / "analyzer.md"
    
    def __init__(self, router: Optional[LLMRouter] = None):
        """
        Args:
            router: LLMRouter instance. لو ما أعطينا، يُنشأ تلقائياً.
        """
        self.router = router or LLMRouter()
        self.system_prompt = self._load_prompt()
    
    def _load_prompt(self) -> str:
        """قراءة الـ Prompt من ملف Markdown."""
        if not self.PROMPT_PATH.exists():
            raise FileNotFoundError(
                f"Prompt file not found: {self.PROMPT_PATH}"
            )
        return self.PROMPT_PATH.read_text(encoding="utf-8")
    
    def _extract_json(self, text: str) -> str:
        """
        استخراج JSON من رد النموذج.
        
        النموذج قد يرجع:
        - JSON نظيف مباشرة ✅
        - JSON محاط بـ ```json ... ``` (نتعامل معه)
        - نص + JSON + نص (نستخرج JSON)
        """
        text = text.strip()
        
        # حالة 1: JSON محاط بـ markdown code block
        # مثال: ```json { ... } ```
        code_block_match = re.search(
            r"```(?:json)?\s*(\{.*?\})\s*```",
            text,
            re.DOTALL,
        )
        if code_block_match:
            return code_block_match.group(1)
        
        # حالة 2: JSON مباشر (يبدأ بـ { وينتهي بـ })
        # نبحث عن أول { وآخر } لضمان صحة الاستخراج
        first_brace = text.find("{")
        last_brace = text.rfind("}")
        
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            return text[first_brace : last_brace + 1]
        
        # لم نجد JSON صالح
        raise ValueError(f"No valid JSON found in response:\n{text[:500]}")
    
    async def analyze(self, transcript: str, context_block: str = "") -> AnalysisResult:
        """
        تحليل نص transcript وإرجاع AnalysisResult منظم.
        
        Args:
            transcript: النص الكامل للتقرير الإخباري
        
        Returns:
            AnalysisResult: كل المعلومات المستخرجة
        
        Raises:
            ValueError: إذا كان transcript فارغاً أو JSON غير صالح
            ValidationError: إذا كانت النتيجة لا تتطابق مع الـ Schema
        """
        if not transcript or not transcript.strip():
            raise ValueError("Transcript cannot be empty")
        
        # بناء الرسالة الكاملة
        user_prompt = f"""{context_block}

حلّل هذا النص الإخباري:

<transcript>
{transcript.strip()}
</transcript>

أرجع JSON فقط بدون أي شيء آخر."""
        
        # الاستدعاء عبر الـ Router (سيوجّه لـ Claude Sonnet 5)
        response = await self.router.generate(
            prompt=user_prompt,
            task=TaskType.TRANSCRIPT_ANALYSIS,
            system=self.system_prompt,
            max_tokens=4000,
        )
        
        # استخراج JSON
        try:
            json_text = self._extract_json(response.text)
        except ValueError as e:
            raise ValueError(
                f"Failed to extract JSON from model response.\n"
                f"Provider: {response.provider}, Model: {response.model}\n"
                f"Raw response:\n{response.text[:1000]}\n\n"
                f"Error: {e}"
            )
        
        # Parse JSON
        try:
            data = json.loads(json_text)
        except json.JSONDecodeError as e:
            raise ValueError(
                f"Invalid JSON:\n{json_text[:1000]}\n\nError: {e}"
            )
        
        # Validation عبر Pydantic
        try:
            result = AnalysisResult(**data)
        except ValidationError as e:
            raise ValueError(
                f"Schema validation failed.\n"
                f"Data: {json.dumps(data, ensure_ascii=False, indent=2)[:1000]}\n\n"
                f"Errors: {e}"
            )
        
        return result


# ---------- اختبار سريع ----------
if __name__ == "__main__":
    import asyncio
    
    # نموذج نص من Syria TV (من الـ PDF اللي حمّلته)
    SAMPLE_TRANSCRIPT = """
    شهدت مدينة الطبقة بريف الرقة وقفة احتجاجية طالب خاللها الأهالي بإصلاحات إدارية شاملة،
    ومحاسبة المتورطين في قضايا فساد، وتحسين مستوى الخدمات العامة والواقع المعيشي.
    كما دعا المشاركون إلى تمكين الكفاءات وإبعاد أصحاب شبهات الفساد عن مواقع المسؤولية،
    مؤكدين أهمية تعزيز الشفافية والاستجابة لمطالب المواطنين.
    
    وقال أحد المشاركين: "نطالب بإصلاح حقيقي وليس مجرد شعارات، فالوضع لم يعد يحتمل."
    وأضاف مشارك آخر أن المدينة تعاني من نقص حاد في الخدمات الأساسية منذ سنوات،
    وأن الحكومة السورية الجديدة يجب أن تتحرك بسرعة لمعالجة هذه المشاكل.
    
    وشارك في الوقفة العشرات من أهالي المدينة، ورفعوا لافتات تطالب بمحاسبة المسؤولين
    السابقين، وضمان توزيع عادل للموارد.
    """
    
    async def test():
        print("[TEST] TranscriptAnalyzer - أول تحليل حقيقي")
        print("=" * 60)
        print(f"Transcript length: {len(SAMPLE_TRANSCRIPT)} chars")
        print("=" * 60)
        
        analyzer = TranscriptAnalyzer()
        
        print("\n[Analyzing...] Sending to Claude Sonnet 5...")
        result = await analyzer.analyze(SAMPLE_TRANSCRIPT)
        
        print("\n[Analysis Complete]")
        print(result.to_display())
        
        # طباعة الإحصائيات
        stats = analyzer.router.get_stats()
        print(f"\n[Cost] ${stats['total_cost_usd']:.6f}")
        print(f"[Tokens] {stats['total_input_tokens']} in, {stats['total_output_tokens']} out")
    
    asyncio.run(test())