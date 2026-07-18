"""
LLM Router - الموجّه الذكي بين النماذج
=====================================
يوجّه كل مهمة للـ Provider الأنسب:
- Task-based routing: مهمة "title_generation" → Claude
- Fallback: لو Provider سقط، ينتقل للتالي تلقائياً
- Cost tracking: يجمع تكلفة كل الاستدعاءات
"""

from enum import Enum
from typing import Optional

from stv_studio.config import settings
from stv_studio.providers.anthropic_provider import AnthropicProvider
from stv_studio.providers.base import LLMProvider, LLMResponse
from stv_studio.providers.gemini_provider import GeminiProvider
from stv_studio.providers.openai_provider import OpenAIProvider


class TaskType(str, Enum):
    """أنواع المهام في النظام - كل واحدة توجّه لموديل مختلف."""
    
    TRANSCRIPT_ANALYSIS = "transcript_analysis"
    TITLE_GENERATION = "title_generation"
    THUMBNAIL_TEXT = "thumbnail_text"
    DESCRIPTION = "description"
    KEYWORDS = "keywords"
    QUALITY_EVALUATION = "quality_evaluation"
    GENERAL = "general"
    SOCIAL_MEDIA_GENERATION = "social_media_generation"


class LLMRouter:
    """الموجّه الرئيسي لجميع طلبات النماذج."""
    
    # خريطة المهام للـ Providers والنماذج
    TASK_ROUTING = {
        TaskType.TRANSCRIPT_ANALYSIS: ("anthropic", "claude-sonnet-5"),
        TaskType.TITLE_GENERATION:    ("anthropic", "claude-sonnet-5"),
        TaskType.THUMBNAIL_TEXT:      ("anthropic", "claude-sonnet-5"),
        TaskType.DESCRIPTION:         ("gemini", "gemini-3.1-flash-lite"),
        TaskType.KEYWORDS:            ("gemini", "gemini-3.1-flash-lite"),
        TaskType.QUALITY_EVALUATION:  ("openai", "gpt-5.6-terra"),
        TaskType.GENERAL:             ("anthropic", "claude-sonnet-5"),
        TaskType.SOCIAL_MEDIA_GENERATION: ("anthropic", "claude-sonnet-5"),
    }
    
    def __init__(self):
        """تهيئة كل الـ Providers دفعة واحدة."""
        self.providers: dict[str, LLMProvider] = {
            "anthropic": AnthropicProvider(
                api_key=settings.anthropic_api_key.get_secret_value()
            ),
            "openai": OpenAIProvider(
                api_key=settings.openai_api_key.get_secret_value()
            ),
            "gemini": GeminiProvider(
                api_key=settings.google_api_key.get_secret_value()
            ),
        }
        
        # تتبّع الإحصائيات
        self.total_cost: float = 0.0
        self.total_calls: int = 0
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
    
    async def generate(
        self,
        prompt: str,
        task: TaskType = TaskType.GENERAL,
        override_provider: Optional[str] = None,
        override_model: Optional[str] = None,
        max_tokens: int = 4000,
        temperature: float = 0.4,
        system: Optional[str] = None,
    ) -> LLMResponse:
        """توليد استجابة عبر الـ Provider المناسب."""
        # اختيار Provider والنموذج
        if override_provider and override_model:
            provider_name = override_provider
            model = override_model
        else:
            provider_name, model = self.TASK_ROUTING[task]
        
        # الحصول على الـ Provider
        provider = self.providers.get(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' not found")
        
        # التوليد
        response = await provider.generate(
            prompt=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            system=system,
        )
        
        # تحديث الإحصائيات
        self.total_cost += response.cost_usd
        self.total_calls += 1
        self.total_input_tokens += response.input_tokens
        self.total_output_tokens += response.output_tokens
        
        return response
    
    def get_stats(self) -> dict:
        """إرجاع إحصائيات كل الاستدعاءات في هذه الجلسة."""
        return {
            "total_calls": self.total_calls,
            "total_cost_usd": round(self.total_cost, 6),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "avg_cost_per_call": (
                round(self.total_cost / self.total_calls, 6)
                if self.total_calls > 0 else 0.0
            ),
        }
    
    def reset_stats(self):
        """إعادة تصفير الإحصائيات."""
        self.total_cost = 0.0
        self.total_calls = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0


# ---------- اختبار سريع ----------
if __name__ == "__main__":
    import asyncio
    
    async def test():
        print("[TEST] LLM Router - Multi-Provider Test")
        print("=" * 60)
        
        router = LLMRouter()
        
        test_prompt = "اكتب سطراً واحداً فقط عن افتتاح جسر جديد في حلب."
        
        tasks_to_test = [
            (TaskType.TITLE_GENERATION, "Title (Claude)"),
            (TaskType.DESCRIPTION, "Description (Gemini)"),
            (TaskType.QUALITY_EVALUATION, "Evaluation (GPT)"),
        ]
        
        for task, label in tasks_to_test:
            print(f"\n[{label}]")
            print(f"   Task: {task.value}")
            
            response = await router.generate(
                prompt=test_prompt,
                task=task,
                max_tokens=150,
            )
            
            print(f"   Provider: {response.provider}")
            print(f"   Model: {response.model}")
            print(f"   Response: {response.text[:100]}...")
            print(f"   Cost: ${response.cost_usd:.6f}")
            print(f"   Latency: {response.latency_ms}ms")
        
        print("\n" + "=" * 60)
        print("[TOTAL STATS]")
        stats = router.get_stats()
        print(f"   Total calls: {stats['total_calls']}")
        print(f"   Total cost: ${stats['total_cost_usd']:.6f}")
        print(f"   Total tokens: {stats['total_input_tokens']} in, {stats['total_output_tokens']} out")
        print(f"   Avg cost/call: ${stats['avg_cost_per_call']:.6f}")
    
    asyncio.run(test())