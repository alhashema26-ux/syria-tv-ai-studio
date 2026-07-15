"""
Anthropic Provider - اتصال بـ Claude API
=========================================
ينفّذ الواجهة `LLMProvider` باستخدام SDK الرسمي من Anthropic.
يدعم كل نماذج Claude الحديثة (Sonnet 5, Opus 4.8, Haiku 4.5, ...).
"""

import time
from typing import Optional

from anthropic import AsyncAnthropic, APIError, APIStatusError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .base import LLMProvider, LLMResponse


class AnthropicProvider(LLMProvider):
    """مزود Claude من Anthropic."""
    
    provider_name = "anthropic"
    
    # الأسعار بالدولار لكل مليون token (يوليو 2026)
    # Sonnet 5 لديه سعر تقديمي حتى 31 أغسطس 2026 ($2/$10)
    # سعر ما بعد ذلك: $3/$15
    PRICING = {
        "claude-sonnet-5": (2.00, 10.00),
        "claude-opus-4-8": (15.00, 75.00),
        "claude-opus-4-7": (15.00, 75.00),
        "claude-opus-4-6": (15.00, 75.00),
        "claude-sonnet-4-6": (3.00, 15.00),
        "claude-haiku-4-5-20251001": (1.00, 5.00),
        "claude-haiku-4-5": (1.00, 5.00),
        "claude-fable-5": (25.00, 125.00),
    }
    
    # النماذج اللي لا تقبل temperature/top_p/top_k
    # تستخدم adaptive thinking داخلياً بدلاً من ذلك
    MODELS_WITHOUT_TEMPERATURE = {
        "claude-sonnet-5",
        "claude-opus-4-7",
        "claude-opus-4-8",
        "claude-fable-5",
    }
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncAnthropic(api_key=api_key)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((APIError, APIStatusError)),
        reraise=True,
    )
    async def generate(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 4000,
        system: Optional[str] = None,
    ) -> LLMResponse:
        """توليد استجابة من Claude."""
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        start_time = time.perf_counter()
        
        # بناء الـ request
        kwargs = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        
        # temperature: النماذج الحديثة (Sonnet 5, Opus 4.7+, Fable 5)
        # لا تقبل temperature — تستخدم adaptive thinking داخلياً
        if model not in self.MODELS_WITHOUT_TEMPERATURE:
            kwargs["temperature"] = temperature
        
        # إضافة system prompt إذا موجود
        if system:
            kwargs["system"] = system
        
        # استدعاء الـ API
        response = await self.client.messages.create(**kwargs)
        
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        # استخراج النص (Claude يرجع list of content blocks)
        # قد يحتوي على thinking blocks + text blocks
        text = ""
        for block in response.content:
            if hasattr(block, "text"):
                text = block.text
                break
        
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        
        return LLMResponse(
            text=text,
            model=model,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            stop_reason=response.stop_reason,
            latency_ms=latency_ms,
        )


# ---------- اختبار سريع ----------
if __name__ == "__main__":
    import asyncio
    
    from stv_studio.config import settings
    
    async def test():
        print("🔵 اختبار Anthropic Provider...")
        print(f"   Model: {settings.anthropic_model}")
        
        provider = AnthropicProvider(
            api_key=settings.anthropic_api_key.get_secret_value()
        )
        
        response = await provider.generate(
            prompt="اكتب عنواناً إخبارياً موجزاً (سطر واحد فقط) عن افتتاح جسر جديد في حلب.",
            model=settings.anthropic_model,
            max_tokens=200,
        )
        
        print(f"\n✅ الاستجابة:")
        print(f"   {response.text}")
        print(f"\n📊 الإحصائيات:")
        print(f"   Tokens: {response.input_tokens} in, {response.output_tokens} out")
        print(f"   Cost:   ${response.cost_usd:.6f}")
        print(f"   Latency: {response.latency_ms}ms")
        print(f"\n🔍 التفاصيل: {response}")
    
    asyncio.run(test())