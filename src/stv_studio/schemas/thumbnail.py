"""
Thumbnail Schema - نتيجة توليد نصوص الصورة المصغّرة
======================================================
Pydantic models للنتيجة من ThumbnailAgent.
"""
from pydantic import BaseModel, Field


class ThumbnailOption(BaseModel):
    """فكرة واحدة لنص الثمبنيل مع بريف تصميم بصري احترافي."""

    text: str = Field(..., min_length=2, max_length=60)
    word_count: int = Field(..., ge=1, le=6)
    visual_note: str = Field(..., min_length=20, max_length=900)


class ThumbnailResult(BaseModel):
    """
    النتيجة الكاملة من ThumbnailAgent.
    10 أفكار (5 بحد أقصى 4 كلمات + 5 حتى 6 كلمات)
    مع بريف تصميم بصري احترافي لكل واحدة.
    """

    options: list[ThumbnailOption] = Field(..., min_length=10, max_length=10)
    recommended_index: int = Field(..., ge=0, le=9)

    def to_display(self) -> str:
        lines = ["=" * 70, "Thumbnail Text Options", "=" * 70, ""]
        for i, opt in enumerate(self.options):
            marker = " ⭐" if i == self.recommended_index else "   "
            lines.append(f"{marker} {i}. {opt.text}  ({opt.word_count} كلمات)")
            lines.append(f"      🖼️  {opt.visual_note}")
            lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)
