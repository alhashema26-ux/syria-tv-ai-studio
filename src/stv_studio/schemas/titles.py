"""
Titles Schema - نتيجة توليد العناوين
======================================
Pydantic models للنتيجة من TitleAgent.
"""

from typing import Optional

from pydantic import BaseModel, Field


class TitleOption(BaseModel):
    """عنوان واحد مع metadata."""
    
    text: str = Field(..., min_length=20, max_length=200)
    style: str = Field(..., max_length=50)
    length: int = Field(..., ge=20, le=200)
    rationale: str = Field(..., max_length=500)


class RecommendedTitle(BaseModel):
    """التوصية بأفضل عنوان."""
    
    index: int = Field(..., ge=0, le=9)
    reason: str = Field(..., min_length=20, max_length=1000)


class TitleGenerationResult(BaseModel):
    """
    النتيجة الكاملة من TitleAgent.
    10 عناوين + توصية بالأقوى.
    """
    
    titles: list[TitleOption] = Field(..., min_length=8, max_length=12)
    recommended: RecommendedTitle
    notes: Optional[str] = Field(default=None, max_length=1000)
    
    def to_display(self) -> str:
        """طباعة منسّقة للعرض."""
        lines = ["=" * 70, "Generated Titles", "=" * 70]
        
        for i, title in enumerate(self.titles):
            marker = " ⭐" if i == self.recommended.index else "   "
            lines.append(f"{marker} {i}. [{title.style}] ({title.length} حرف)")
            lines.append(f"      {title.text}")
            lines.append(f"      → {title.rationale}")
            lines.append("")
        
        lines.append("=" * 70)
        lines.append(f"⭐ Recommended: #{self.recommended.index}")
        lines.append(f"   {self.titles[self.recommended.index].text}")
        lines.append(f"   Reason: {self.recommended.reason}")
        
        if self.notes:
            lines.append("")
            lines.append(f"Notes: {self.notes}")
        
        lines.append("=" * 70)
        return "\n".join(lines)