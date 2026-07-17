"""
Description Schema - نتيجة توليد الوصف
=========================================
Pydantic models للنتيجة من DescriptionAgent.
"""
from typing import Optional
from pydantic import BaseModel, Field


class DescriptionResult(BaseModel):
    """
    النتيجة الكاملة من DescriptionAgent.
    وصف يوتيوب + كلمات مفتاحية + هاشتاغات.
    """

    description: str = Field(..., min_length=100, max_length=2000)
    keywords: list[str] = Field(..., min_length=8, max_length=25)
    hashtags: list[str] = Field(..., min_length=5, max_length=15)
    notes: Optional[str] = Field(default=None, max_length=500)

    def to_display(self) -> str:
        """طباعة منسّقة للعرض."""
        lines = ["=" * 70, "Generated Description", "=" * 70, ""]

        lines.append("📄 الوصف:")
        lines.append(self.description)
        lines.append("")

        lines.append(f"🔑 الكلمات المفتاحية ({len(self.keywords)}):")
        lines.append(", ".join(self.keywords))
        lines.append("")

        lines.append(f"#️⃣ الهاشتاغات ({len(self.hashtags)}):")
        lines.append(" ".join(self.hashtags))

        if self.notes:
            lines.append("")
            lines.append(f"Notes: {self.notes}")

        lines.append("=" * 70)
        return "\n".join(lines)
