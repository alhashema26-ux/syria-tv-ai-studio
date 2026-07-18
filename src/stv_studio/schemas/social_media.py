"""
Social Media Schema - نتيجة توليد حزمة النشر متعددة المنصات
================================================================
Pydantic models للنتيجة من SocialMediaAgent.
يغطي: فيسبوك، إنستغرام، إكس، تلغرام، واتساب، تيك توك.
حدود الطول لكل حقل مطابقة تماماً لحدود كل منصة الفعلية.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field

NewsType = Literal[
    "عاجل",
    "تقرير-تحليل",
    "مداخلة-تصريح",
    "متابعة-تطور",
    "إنساني-قصة",
    "اقتصادي-أرقام",
]

HookPattern = Literal[
    "Pattern Interrupt",
    "Curiosity Gap",
    "Contradiction",
    "Number Tease",
    "Direct Question",
    "Shock Statement",
]


class InternalClassification(BaseModel):
    """التصنيف الداخلي للمدخل ونوع الخبر."""

    input_type: str = Field(..., max_length=50)
    news_type: NewsType
    chosen_angle: str = Field(..., max_length=300)
    target_audience: str = Field(..., max_length=100)


class FacebookContent(BaseModel):
    # العنوان: 60-90 حرف (نسمح هامش أمان حتى 110)
    titles: list[str] = Field(..., min_length=3, max_length=3)
    # الكابشن: 150-400 حرف (هامش أمان حتى 450)
    captions: list[str] = Field(..., min_length=3, max_length=3)
    hashtags: list[str] = Field(..., min_length=3, max_length=5)


class InstagramHook(BaseModel):
    text: str = Field(..., max_length=140)  # ≤125 + هامش أمان
    pattern: HookPattern


class InstagramContent(BaseModel):
    hooks: list[InstagramHook] = Field(..., min_length=3, max_length=3)
    full_caption: str = Field(..., max_length=850)  # 300-800 + هامش
    hashtags: list[str] = Field(..., min_length=5, max_length=8)


class XContent(BaseModel):
    # الحد الأصعب تقنياً: 280 حرف بالضبط (حد منصة X نفسه، بدون هامش)
    tweets: list[str] = Field(..., min_length=3, max_length=3)
    thread_suggestion: str = Field(..., max_length=500)
    hashtags: list[str] = Field(..., min_length=0, max_length=2)


class TelegramContent(BaseModel):
    # 400-1200 حرف + هامش
    captions: list[str] = Field(..., min_length=3, max_length=3)
    hashtags: list[str] = Field(..., min_length=2, max_length=3)


class WhatsAppContent(BaseModel):
    # 80-250 حرف + هامش
    captions: list[str] = Field(..., min_length=3, max_length=3)
    emojis_used: list[str] = Field(default_factory=list, max_length=2)


class TikTokHook(BaseModel):
    text: str = Field(..., max_length=200)
    pattern: HookPattern


class TikTokContent(BaseModel):
    hooks: list[TikTokHook] = Field(..., min_length=3, max_length=3)
    full_caption: str = Field(..., max_length=350)  # 100-300 + هامش
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

    def validate_x_char_limits(self) -> list[str]:
        """
        تحقق إضافي صارم لحد X (280 حرف)، لأنه حد تقني حقيقي
        (منصة X ترفض أي تغريدة أطول)، وليس مجرد توصية أسلوبية.
        يرجع قائمة تحذيرات إن وُجدت (لا يرفع استثناء).
        """
        warnings = []
        for i, tweet in enumerate(self.x_twitter.tweets):
            if len(tweet) > 280:
                warnings.append(
                    f"تغريدة #{i+1} تتجاوز حد X (280 حرف): طولها الفعلي {len(tweet)} حرف"
                )
        return warnings

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

        x_warnings = self.validate_x_char_limits()
        if x_warnings:
            lines.append("")
            lines.append("⚠️  تحذيرات:")
            for w in x_warnings:
                lines.append(f"  - {w}")

        lines.append("")
        lines.append("Editor Notes:")
        for note in self.editor_notes:
            lines.append(f"  • {note}")
        lines.append("=" * 70)
        return "\n".join(lines)
