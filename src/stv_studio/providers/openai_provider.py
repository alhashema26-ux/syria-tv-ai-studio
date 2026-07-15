"""
OpenAI Provider - اتصال بـ GPT API
====================================
ينفّذ الواجهة LLMProvider باستخدام SDK الرسمي من OpenAI.
يدعم كل نماذج GPT الحديثة (GPT-5.6 Sol, Terra, Luna).
"""

import time
from typing import Optional

from openai import AsyncOpenAI, APIError, APIStatusError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .base import LLMProvider, LLMResponse


class OpenAIProvider(LLMProvider):
    """مزود GPT من OpenAI."""
    
    provider_name = "openai"
    
    # الأسعار بالدولار لكل مليون token (يوليو 2026)
    PRICING = {
        # GPT-5.6 family (الأحدث)
        "gpt-5.6": (5.00, 30.00),
        "gpt-5.6-sol": (5.00, 30.00),
        "gpt-5.6-terra": (2.50, 15.00),
        "gpt-5.6-luna": (1.00, 6.00),
        
        # GPT-5.5 family
        "gpt-5.5": (5.00, 30.00),
        "gpt-5.5-pro": (30.00, 180.00),
        
        # GPT-5.4
        "gpt-5.4": (2.50, 15.00),
    }
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncOpenAI(api_key=api_key)
    
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
        """توليد استجابة من GPT."""
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        start_time = time.perf_counter()
        
        # بناء الـ messages
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        
        # بناء الـ request
        kwargs = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }
        
        # GPT-5.x تفرض temperature=1 (الافتراضية)
        # النماذج القديمة (GPT-4) تقبل temperature عادي
        if not model.startswith("gpt-5"):
            kwargs["temperature"] = temperature
        
        # استدعاء الـ API
        response = await self.client.chat.completions.create(**kwargs)
        
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        # استخراج النص
        text = response.choices[0].message.content or ""
        
        # استخراج الـ tokens
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens
        
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        
        return LLMResponse(
            text=text,
            model=model,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            stop_reason=response.choices[0].finish_reason,
            latency_ms=latency_ms,
        )


# ---------- اختبار سريع ----------
if __name__ == "__main__":
    import asyncio
    
    from stv_studio.config import settings
    
    async def test():
        print("[TEST] OpenAI Provider")
        print(f"   Model: {settings.openai_model}")
        
        provider = OpenAIProvider(
            api_key=settings.openai_api_key.get_secret_value()
        )
        
        response = await provider.generate(
            prompt="اكتب عنواناً إخبارياً موجزاً (سطر واحد فقط) عن افتتاح جسر جديد في حلب.",
            model=settings.openai_model,
            max_tokens=200,
        )
        
        print(f"\n[Response]")
        print(f"   {response.text}")
        print(f"\n[Stats]")
        print(f"   Tokens: {response.input_tokens} in, {response.output_tokens} out")
        print(f"   Cost:   ${response.cost_usd:.6f}")
        print(f"   Latency: {response.latency_ms}ms")
        print(f"\n[Details] {response}")
    
    asyncio.run(test())