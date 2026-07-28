"""
OpenRouter Provider - وصول لكل النماذج من مكان واحد
====================================================
متوافق مع OpenAI API format.
يدعم: claude-opus-4.8, gemini-2.5-pro, gpt-4o, وغيرها.
"""

import time
from typing import Optional

from openai import AsyncOpenAI, APIError, APIStatusError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .base import LLMProvider, LLMResponse


class OpenRouterProvider(LLMProvider):
    """مزود OpenRouter — كل النماذج من API واحدة."""

    provider_name = "openrouter"

    # تكلفة تقريبية (OpenRouter يضيف هامش صغير)
    PRICING = {
        "anthropic/claude-opus-4.8":     (15.00, 75.00),
        "anthropic/claude-opus-4-6":     (15.00, 75.00),
        "anthropic/claude-sonnet-4-6":   (3.00,  15.00),
        "openai/gpt-4o":                 (2.50,  10.00),
        "openai/gpt-4o-mini":            (0.15,   0.60),
        "google/gemini-2.5-pro":         (1.25,  10.00),
        "google/gemini-2.5-flash":       (0.075,  0.30),
    }

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
        )

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
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        start = time.time()
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = int((time.time() - start) * 1000)

        text = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        # حساب التكلفة
        pricing = self.PRICING.get(model, (1.0, 1.0))
        cost = (input_tokens * pricing[0] + output_tokens * pricing[1]) / 1_000_000

        return LLMResponse(
            text=text,
            provider=self.provider_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )
