"""
Gemini Provider - اتصال بـ Google Gemini API
=============================================
ينفّذ الواجهة LLMProvider باستخدام SDK الرسمي الجديد من Google (google-genai).
يدعم كل نماذج Gemini الحديثة (3.5 Flash, 3.1 Pro, 3.1 Flash-Lite).
"""

import time
from typing import Optional

from google import genai
from google.genai import types as genai_types
from google.genai.errors import APIError, ServerError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from .base import LLMProvider, LLMResponse


class GeminiProvider(LLMProvider):
    """مزود Gemini من Google."""
    
    provider_name = "gemini"
    
    # الأسعار بالدولار لكل مليون token (يوليو 2026)
    PRICING = {
        # Gemini 3.5 (الأحدث)
        "gemini-3.5-flash": (1.50, 9.00),
        
        # Gemini 3.1 family
        "gemini-3.1-pro": (2.00, 12.00),
        "gemini-3.1-flash-lite": (0.10, 0.40),
        
        # Gemini 2.5 (لا زال متاح)
        "gemini-2.5-pro": (1.25, 10.00),
        "gemini-2.5-flash": (0.30, 2.50),
        "gemini-2.5-flash-lite": (0.10, 0.40),
    }
    
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = genai.Client(api_key=api_key)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((APIError, ServerError)),
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
        """توليد استجابة من Gemini."""
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty")
        
        start_time = time.perf_counter()
        
        # بناء الإعدادات
        config = genai_types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        
        # إضافة system prompt إذا موجود
        if system:
            config.system_instruction = system
        
        # استدعاء الـ API (async version)
        response = await self.client.aio.models.generate_content(
            model=model,
            contents=prompt,
            config=config,
        )
        
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        
        # استخراج النص
        text = response.text or ""
        
        # استخراج الـ tokens
        usage = response.usage_metadata
        input_tokens = usage.prompt_token_count if usage else 0
        output_tokens = usage.candidates_token_count if usage else 0
        
        cost = self.calculate_cost(model, input_tokens, output_tokens)
        
        # سبب التوقف
        stop_reason = None
        if response.candidates and response.candidates[0].finish_reason:
            stop_reason = str(response.candidates[0].finish_reason)
        
        return LLMResponse(
            text=text,
            model=model,
            provider=self.provider_name,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            stop_reason=stop_reason,
            latency_ms=latency_ms,
        )


# ---------- اختبار سريع ----------
if __name__ == "__main__":
    import asyncio
    
    from stv_studio.config import settings
    
    async def test():
        print("[TEST] Gemini Provider")
        print(f"   Model: {settings.gemini_model}")
        
        provider = GeminiProvider(
            api_key=settings.google_api_key.get_secret_value()
        )
        
        response = await provider.generate(
            prompt="اكتب عنواناً إخبارياً موجزاً (سطر واحد فقط) عن افتتاح جسر جديد في حلب.",
            model=settings.gemini_model,
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