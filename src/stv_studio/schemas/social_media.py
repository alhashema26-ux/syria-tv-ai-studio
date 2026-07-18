"""
Social Media Schema - نتيجة توليد حزمة النشر متعددة المنصات
================================================================
Pydantic models للنتيجة من SocialMediaAgent.
يغطي: فيسبوك، إنستغرام، إكس، تلغرام، واتساب، تيك توك.
"""
from typing import Optional
from pydantic import BaseModel, Field


class InternalClassification(BaseModel):
    """التصنيف الداخلي للمدخل ونوع الخبر."""

    input_type: str = Field(..., max_length=50)
    news_type: str = Field(..., max_length=50)
    chosen_angle: str = Field(..., max_length=300)
    target_audience: str = Field(..., max_length=100)


class FacebookContent(BaseModel):
    titles: list[str] = Field(..., min_length=3, max_length=3)
    captions: list[str] = Field(..., min_length=3, max_length=3)
    hashtags: list[str] = Field(..., min_length=3, max_length=5)


class InstagramHook(BaseModel):
    text: str = Field(..., max_length=200)
    pattern: str = Field(..., max_length=50)


class InstagramContent(BaseModel):
    hooks: list[InstagramHook] = Field(..., min_length=3, max_length=3)
    full_caption: str = Field(..., max_length=1000)
    hashtags: list[str] = Field(..., min_length=5, max_length=8)


class XContent(BaseModel):
    tweets: list[str] = Field(..., min_length=3, max_length=3)
    thread_suggestion: str = Field(..., max_length=500)
    hashtags: list[str] = Field(..., min_length=0, max_length=2)


class TelegramContent(BaseModel):
    captions: list[str] = Field(..., min_length=3, max_length=3)
    hashtags: list[str] = Field(..., min_length=2, max_length=3)


class WhatsAppContent(BaseModel):
    captions: list[str] = Field(..., min_length=3, max_length=3)
    emojis_used: list[str] = Field(default_factory=list, max_length=2)


class TikTokHook(BaseModel):
    text: str = Field(..., max_length=200)
    pattern: str = Field(..., max_length=50)


class TikTokContent(BaseModel):
    hooks: list[TikTokHook] = Field(..., min_length=3, max_length=3)
    full_caption: str = Field(..., max_length=400)
    hashtags: list[str] = Field(..., min_length=4, max_length=6)


class SocialMediaResult(BaseModel):
    """
    النتيجة الكاملة من SocialMediaAgent — حزمة نشر لست منصات.
    """

    classification: InternalClassification
    facebook: FacebookContent
    instagram: InstagramContent
    x_twitter: XContent
    telegram: TelegramContent
    whatsapp: WhatsAppContent
    tiktok: TikTokContent
    editor_notes: list[str] = Field(..., min_length=1, max_length=4)

    def to_display(self) -> str:
        lines = ["=" * 70, "Social Media Content Package", "=" * 70, ""]
        lines.append(f"[التصنيف: {self.classification.news_type} | {self.classification.chosen_angle}]")
        lines.append("")
        lines.append(f"📘 Facebook: {len(self.facebook.titles)} عناوين, {len(self.facebook.captions)} كابشن")
        lines.append(f"📸 Instagram: {len(self.instagram.hooks)} هوكات")
        lines.append(f"✖️  X: {len(self.x_twitter.tweets)} تغريدات")
        lines.append(f"✈️  Telegram: {len(self.telegram.captions)} نسخ")
        lines.append(f"💬 WhatsApp: {len(self.whatsapp.captions)} نسخ")
        lines.append(f"🎵 TikTok: {len(self.tiktok.hooks)} هوكات")
        lines.append("")
        lines.append("Editor Notes:")
        for note in self.editor_notes:
            lines.append(f"  • {note}")
        lines.append("=" * 70)
        return "\n".join(lines)
