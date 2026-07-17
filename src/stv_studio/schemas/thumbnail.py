"""
Thumbnail Schema - نتيجة توليد نصوص الصورة المصغّرة
======================================================
Pydantic models للنتيجة من ThumbnailAgent.
"""
from pydantic import BaseModel, Field


class ThumbnailOption(BaseModel):
    """فكرة واحدة لنص الثمبنيل."""

    text: str = Field(..., min_length=2, max_length=40)
    visual_note: str = Field(..., max_length=200)


class ThumbnailResult(BaseModel):
    """
    النتيجة الكاملة من ThumbnailAgent.
    5 أفكار لنص الصورة المصغّرة + ملاحظة بصرية لكل واحدة.
    """

    options: list[ThumbnailOption] = Field(..., min_length=3, max_length=6)
    recommended_index: int = Field(..., ge=0, le=5)

    def to_display(self) -> str:
        lines = ["=" * 70, "Thumbnail Text Options", "=" * 70, ""]
        for i, opt in enumerate(self.options):
            marker = " ⭐" if i == self.recommended_index else "   "
            lines.append(f"{marker} {i}. {opt.text}")
            lines.append(f"      🖼️  {opt.visual_note}")
            lines.append("")
        lines.append("=" * 70)
        return "\n".join(lines)
