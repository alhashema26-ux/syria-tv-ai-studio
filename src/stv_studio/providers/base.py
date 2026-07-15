"""
Base LLM Provider - العقد الموحّد لكل النماذج
=============================================
كل Provider (Anthropic, OpenAI, Gemini) يورث من هذا الـ Class،
ويلتزم بنفس الواجهة. هذا يمكّننا من استبدال أي نموذج بآخر
بدون تغيير أي كود يستخدمه.
"""

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field


class LLMResponse(BaseModel):
    """
    الاستجابة الموحّدة من أي نموذج.
    كل Provider يرجع هذا النوع، بغض النظر عن الـ SDK الأصلي.
    """
    
    text: str = Field(..., description="النص الناتج من النموذج")
    model: str = Field(..., description="اسم النموذج المستخدم")
    provider: str = Field(..., description="اسم مزود النموذج (anthropic/openai/gemini)")
    
    # Token usage
    input_tokens: int = Field(..., ge=0, description="عدد tokens المدخلة")
    output_tokens: int = Field(..., ge=0, description="عدد tokens المخرجة")
    
    # Cost tracking
    cost_usd: float = Field(..., ge=0.0, description="التكلفة بالدولار")
    
    # Optional metadata
    stop_reason: Optional[str] = Field(default=None, description="سبب توقف التوليد")
    latency_ms: Optional[int] = Field(default=None, description="الزمن بالميلي ثانية")
    
    def __str__(self) -> str:
        """طباعة مختصرة للتصحيح"""
        return (
            f"LLMResponse(provider={self.provider}, model={self.model}, "
            f"tokens={self.input_tokens}+{self.output_tokens}, "
            f"cost=${self.cost_usd:.4f})"
        )


class LLMProvider(ABC):
    """
    الواجهة الأساسية لأي مزود نموذج.
    
    كل Provider جديد (Anthropic, OpenAI, Gemini, ...) لازم:
    1. يرث من هذا الـ Class
    2. يعرّف الـ `provider_name` و `PRICING`
    3. ينفّذ `generate()` بشكل async
    """
    
    # يجب على كل Provider تحديد هذا (مثلاً: "anthropic")
    provider_name: str = ""
    
    # جدول الأسعار: {model_name: (input_price_per_1M, output_price_per_1M)}
    # الأسعار بالدولار لكل مليون token
    PRICING: dict[str, tuple[float, float]] = {}
    
    def __init__(self, api_key: str):
        """
        Args:
            api_key: مفتاح API للمزود
        """
        if not api_key:
            raise ValueError(f"{self.provider_name}: API key is required")
        self.api_key = api_key
    
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        model: str,
        temperature: float = 0.4,
        max_tokens: int = 4000,
        system: Optional[str] = None,
    ) -> LLMResponse:
        """
        توليد استجابة من النموذج.
        
        Args:
            prompt: النص المدخل (رسالة المستخدم)
            model: اسم النموذج (مثل "claude-sonnet-5")
            temperature: عشوائية التوليد (0.0-2.0)
            max_tokens: أقصى عدد tokens للاستجابة
            system: تعليمات نظامية اختيارية (system prompt)
        
        Returns:
            LLMResponse: الاستجابة الموحّدة
        
        Raises:
            ValueError: إذا كان النموذج غير مدعوم
            Exception: أي خطأ من الـ API
        """
        ...
    
    def calculate_cost(
        self, 
        model: str, 
        input_tokens: int, 
        output_tokens: int
    ) -> float:
        """
        حساب التكلفة بالدولار بناءً على جدول الأسعار.
        
        Args:
            model: اسم النموذج
            input_tokens: عدد الـ tokens المدخلة
            output_tokens: عدد الـ tokens المخرجة
        
        Returns:
            التكلفة بالدولار (0.0 إذا النموذج غير مسعّر)
        """
        if model not in self.PRICING:
            return 0.0
        
        input_price, output_price = self.PRICING[model]
        # الأسعار لكل مليون token
        cost = (
            (input_tokens / 1_000_000) * input_price
            + (output_tokens / 1_000_000) * output_price
        )
        return round(cost, 6)  # 6 خانات عشرية لدقة عالية
    
    def __repr__(self) -> str:
        """للتصحيح — لا يكشف الـ API key"""
        return f"{self.__class__.__name__}(provider={self.provider_name})"