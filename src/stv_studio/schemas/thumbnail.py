"""
Thumbnail Schema - نتيجة توليد نصوص الصورة المصغّرة
======================================================
Pydantic models للنتيجة من ThumbnailAgent.
نص فقط، بأسلوب إخباري جاد، بدون بريف تصميم بصري.
"""
from pydantic import BaseModel, Field


class ThumbnailOption(BaseModel):
    """فكرة واحدة لنص الثمبنيل — نص فقط."""

    text: str = Field(..., min_length=2, max_length=40)
    word_count: int = Field(..., ge=1, le=6)


class ThumbnailResult(BaseModel):
    """
    النتيجة الكاملة من ThumbnailAgent.
    10 أفكار نصية قصيرة (4-6 كلمات)، بأسلوب إخباري جاد.
    """

    options: list[ThumbnailOption] = Field(..., min_length=10, max_length=10)
    recommended_index: int = Field(..., ge=0, le=9)

    def to_display(self) -> str:
        lines = ["=" * 70, "Thumbnail Text Options", "=" * 70, ""]
        for i, opt in enumerate(self.options):
            marker = " ⭐" if i == self.recommended_index else "   "
            lines.append(f"{marker} {i}. {opt.text}  ({opt.word_count} كلمات)")
        lines.append("=" * 70)
        return "\n".join(lines)
