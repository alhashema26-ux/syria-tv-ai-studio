"""
Evaluation Schema - نتيجة تقييم الجودة
==========================================
Pydantic models للنتيجة من QualityEvaluator.
"""
from typing import Optional
from pydantic import BaseModel, Field


class CriterionScore(BaseModel):
    """تقييم معيار واحد من معايير الجودة."""

    name: str = Field(..., max_length=50)
    score: int = Field(..., ge=0, le=100)
    comment: str = Field(..., max_length=800)


class EvaluationResult(BaseModel):
    """
    النتيجة الكاملة من QualityEvaluator.
    تقييم شامل للعنوان + الوصف + الثمبنيل المُختارين، من نموذج مختلف عن المولّد.
    """

    overall_score: int = Field(..., ge=0, le=100)
    criteria: list[CriterionScore] = Field(..., min_length=4, max_length=8)
    strengths: list[str] = Field(..., min_length=1, max_length=8)
    weaknesses: list[str] = Field(default_factory=list, max_length=8)
    verdict: str = Field(..., max_length=200)
    ready_to_publish: bool

    def to_display(self) -> str:
        lines = ["=" * 70, "Quality Evaluation", "=" * 70, ""]
        lines.append(f"📊 التقييم الإجمالي: {self.overall_score}/100")
        lines.append(f"🏁 الحكم: {self.verdict}")
        lines.append(f"✅ جاهز للنشر: {'نعم' if self.ready_to_publish else 'لا'}")
        lines.append("")

        lines.append("المعايير التفصيلية:")
        for c in self.criteria:
            lines.append(f"  • {c.name}: {c.score}/100 — {c.comment}")
        lines.append("")

        lines.append("نقاط القوة:")
        for s in self.strengths:
            lines.append(f"  + {s}")

        if self.weaknesses:
            lines.append("")
            lines.append("نقاط الضعف:")
            for w in self.weaknesses:
                lines.append(f"  - {w}")

        lines.append("=" * 70)
        return "\n".join(lines)
