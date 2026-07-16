"""
STV Studio - Configuration Module
==================================
يقرأ المتغيرات من ملف .env مع التحقق من صحتها.
Type-safe عبر Pydantic v2.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


# المسار الجذري للمشروع (يُحسب تلقائياً من موقع هذا الملف)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """
    إعدادات النظام - تُحمَّل تلقائياً من .env
    
    الاستخدام:
        from stv_studio.config import settings
        print(settings.default_model)
    """
    
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,       # ANTHROPIC_API_KEY == anthropic_api_key
        extra="ignore",              # تجاهل أي متغير إضافي في .env
    )
    
    # --- LLM Providers (SecretStr = لا تظهر في logs أو errors) ---
    anthropic_api_key: SecretStr = Field(
        ..., 
        description="مفتاح Anthropic Claude API"
    )
    openai_api_key: SecretStr = Field(
        ..., 
        description="مفتاح OpenAI API"
    )
    google_api_key: SecretStr = Field(
        ..., 
        description="مفتاح Google Gemini API"
    )
    voyage_api_key: SecretStr = Field(
        ...,
        description="مفتاح Voyage AI للـ embeddings"
    )
    # --- Default Models ---
    default_provider: Literal["anthropic", "openai", "gemini"] = "anthropic"
    anthropic_model: str = "claude-sonnet-5"
    openai_model: str = "gpt-5.6-terra"
    gemini_model: str = "gemini-3.1-flash-lite"
    voyage_model: str = "voyage-3"
    embedding_dimensions: int = 1024

    
    # --- Generation Settings ---
    temperature: float = Field(default=0.4, ge=0.0, le=2.0)
    max_tokens: int = Field(default=4000, ge=1, le=200000)
    
    # --- Logging ---
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"


# Singleton instance - يُحمَّل مرة واحدة عند أول import
settings = Settings()


if __name__ == "__main__":
    # للاختبار السريع: python -m stv_studio.config
    print("✅ Settings loaded successfully")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Default provider: {settings.default_provider}")
    print(f"Anthropic model: {settings.anthropic_model}")
    print(f"OpenAI model: {settings.openai_model}")
    print(f"Gemini model: {settings.gemini_model}")
    print(f"Temperature: {settings.temperature}")
    print(f"Max tokens: {settings.max_tokens}")
    print(f"Log level: {settings.log_level}")
    print(f"\n🔒 API Keys (masked):")
    print(f"  Anthropic: {'*' * 8}{settings.anthropic_api_key.get_secret_value()[-4:]}")
    print(f"  OpenAI:    {'*' * 8}{settings.openai_api_key.get_secret_value()[-4:]}")
    print(f"  Google:    {'*' * 8}{settings.google_api_key.get_secret_value()[-4:]}")