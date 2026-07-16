"""
Analysis Schema - نتيجة تحليل نص إخباري
==========================================
تعريف Pydantic للـ JSON اللي يرجعه TranscriptAnalyzer.
"""

from typing import Optional

from pydantic import BaseModel, Field


class AnalysisResult(BaseModel):
    """نتيجة تحليل نص إخباري."""
    
    # الفهم الأساسي
    topic: str = Field(..., min_length=5, max_length=200)
    category: str = Field(..., max_length=50)
    tone: str = Field(..., max_length=50)
    summary: str = Field(..., min_length=50, max_length=800)
    
    # الكيانات
    people: list[str] = Field(default_factory=list)
    organizations: list[str] = Field(default_factory=list)
    countries: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    
    # SEO
    keywords: list[str] = Field(default_factory=list, max_length=20)
    important_quotes: list[str] = Field(default_factory=list)
    
    # التوجيه التحريري
    youtube_angle: str = Field(..., min_length=20, max_length=300)
    title_focus: str = Field(..., min_length=10, max_length=200)
    thumbnail_focus: str = Field(..., min_length=10, max_length=200)
    
    # السياق
    search_intent: str = Field(..., max_length=200)
    emotion: str = Field(..., max_length=50)
    
    # اختيارية
    urgency_level: Optional[str] = None
    target_audience: Optional[str] = None
    
    def to_display(self) -> str:
        """طباعة منسّقة للـ Terminal."""
        lines = [
            "=" * 60,
            f"Topic:      {self.topic}",
            f"Category:   {self.category}",
            f"Tone:       {self.tone}",
            f"Emotion:    {self.emotion}",
            "",
            f"Summary:    {self.summary}",
            "",
            f"People:     {', '.join(self.people) if self.people else 'N/A'}",
            f"Orgs:       {', '.join(self.organizations) if self.organizations else 'N/A'}",
            f"Countries:  {', '.join(self.countries) if self.countries else 'N/A'}",
            f"Locations:  {', '.join(self.locations) if self.locations else 'N/A'}",
            "",
            f"Keywords:   {', '.join(self.keywords[:10])}",
            "",
            f"YT Angle:   {self.youtube_angle}",
            f"Title Focus: {self.title_focus}",
            f"Thumb Focus: {self.thumbnail_focus}",
            "=" * 60,
        ]
        return "\n".join(lines)


# اختبار
if __name__ == "__main__":
    example = AnalysisResult(
        topic="افتتاح جسر جديد في حلب",
        category="بنية تحتية",
        tone="اخباري",
        summary="افتتح جسر جديد في مدينة حلب لتسهيل حركة المرور بين الاحياء الشرقية والغربية بعد سنوات من انقطاع الطرق بسبب الحرب.",
        people=["المهندس احمد فلان", "المحافظ سليم علاني"],
        organizations=["وزارة النقل", "بلدية حلب"],
        countries=["سوريا"],
        locations=["حلب", "حي الاشرفية", "حي الفرقان"],
        keywords=["جسر حلب", "افتتاح جسر", "بنية تحتية سوريا", "اعادة اعمار", "حلب اليوم"],
        important_quotes=["هذا الجسر بداية عودة الحياة"],
        youtube_angle="عودة الحياة الى حلب من خلال مشاريع البنية التحتية",
        title_focus="اول جسر جديد في حلب بعد الحرب",
        thumbnail_focus="لقطة الجسر الجديد مع رمز حلب",
        search_intent="informational",
        emotion="امل",
        urgency_level="مهم",
        target_audience="سوريون + عرب",
    )
    
    print(example.to_display())