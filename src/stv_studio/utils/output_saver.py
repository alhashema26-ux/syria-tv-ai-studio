"""
Output Saver - يحفظ النتائج في ملفات Markdown
"""

from datetime import datetime
from pathlib import Path
from typing import Optional

from stv_studio.config import PROJECT_ROOT
from stv_studio.schemas.analysis import AnalysisResult
from stv_studio.schemas.titles import TitleGenerationResult


class OutputSaver:
    """يحفظ نتائج المعالجة في ملفات Markdown."""
    
    OUTPUT_DIR = PROJECT_ROOT / "outputs"
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = Path(output_dir) if output_dir else self.OUTPUT_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    
    def _format_list(self, items: list) -> str:
        if not items:
            return "_لا يوجد_"
        return ", ".join(items)
    
    def save_full_report(
        self,
        transcript: str,
        analysis: AnalysisResult,
        titles: TitleGenerationResult,
        cost_usd: float,
        input_tokens: int,
        output_tokens: int,
    ) -> Path:
        """حفظ تقرير كامل: نص أصلي + تحليل + عناوين."""
        
        timestamp = self._timestamp()
        filename = "report_" + timestamp + ".md"
        filepath = self.output_dir / filename
        
        # بناء المحتوى قطعة قطعة (أسلم من f-string كبير)
        parts = []
        
        # Header
        parts.append("# تقرير معالجة تلفزيون سوريا")
        parts.append("")
        parts.append("**التاريخ:** " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        parts.append("**التكلفة:** $" + f"{cost_usd:.6f}")
        parts.append("**Tokens:** " + str(input_tokens) + " in, " + str(output_tokens) + " out")
        parts.append("")
        parts.append("---")
        parts.append("")
        
        # النص الأصلي
        parts.append("## 📝 النص الأصلي")
        parts.append("")
        parts.append("```")
        parts.append(transcript.strip())
        parts.append("```")
        parts.append("")
        parts.append("---")
        parts.append("")
        
        # التحليل - الفهم الأساسي
        parts.append("## 🔍 التحليل")
        parts.append("")
        parts.append("### الفهم الأساسي")
        parts.append("")
        parts.append("- **الموضوع:** " + analysis.topic)
        parts.append("- **التصنيف:** " + analysis.category)
        parts.append("- **النبرة:** " + analysis.tone)
        parts.append("- **الشعور:** " + analysis.emotion)
        parts.append("- **مستوى الأولوية:** " + (analysis.urgency_level or "غير محدد"))
        parts.append("- **الجمهور المستهدف:** " + (analysis.target_audience or "غير محدد"))
        parts.append("")
        
        # الملخص
        parts.append("### الملخص")
        parts.append("")
        parts.append(analysis.summary)
        parts.append("")
        
        # الكيانات
        parts.append("### الكيانات المستخرجة")
        parts.append("")
        parts.append("| النوع | القيم |")
        parts.append("|---|---|")
        parts.append("| **أشخاص** | " + self._format_list(analysis.people) + " |")
        parts.append("| **منظمات** | " + self._format_list(analysis.organizations) + " |")
        parts.append("| **دول** | " + self._format_list(analysis.countries) + " |")
        parts.append("| **أماكن** | " + self._format_list(analysis.locations) + " |")
        parts.append("")
        
        # الكلمات المفتاحية
        parts.append("### الكلمات المفتاحية")
        parts.append("")
        parts.append(self._format_list(analysis.keywords))
        parts.append("")
        
        # الاقتباسات
        parts.append("### الاقتباسات المهمة")
        parts.append("")
        if analysis.important_quotes:
            for quote in analysis.important_quotes:
                parts.append("> " + quote)
                parts.append("")
        else:
            parts.append("_لا توجد اقتباسات مباشرة_")
            parts.append("")
        
        # التوجيه التحريري
        parts.append("### التوجيه التحريري")
        parts.append("")
        parts.append("- **زاوية YouTube:** " + analysis.youtube_angle)
        parts.append("- **تركيز العنوان:** " + analysis.title_focus)
        parts.append("- **تركيز الـ Thumbnail:** " + analysis.thumbnail_focus)
        parts.append("- **نية البحث:** " + analysis.search_intent)
        parts.append("")
        parts.append("---")
        parts.append("")
        
        # العناوين
        parts.append("## 🎯 العناوين المقترحة")
        parts.append("")

        if not titles:
            parts.append("لم يتم توليد عناوين.")
            parts.append("")
        else:
         for i, title in enumerate(titles.titles):
            is_recommended = (i == titles.recommended.index)
            marker = "⭐ " if is_recommended else ""
            
            parts.append("### " + marker + "#" + str(i) + " — " + title.style)
            parts.append("")
            parts.append("**العنوان:** " + title.text)
            parts.append("")
            parts.append("**الطول:** " + str(title.length) + " حرف")
            parts.append("")
            parts.append("**المبرر:** " + title.rationale)
            parts.append("")
            parts.append("---")
            parts.append("")
        
        # التوصية
        parts.append("## ⭐ التوصية النهائية")
        parts.append("")
        parts.append("**العنوان الموصى به (#" + str(titles.recommended.index) + "):**")
        parts.append("")
        parts.append("> " + titles.titles[titles.recommended.index].text)
        parts.append("")
        parts.append("**السبب:**")
        parts.append("")
        parts.append(titles.recommended.reason)
        parts.append("")
        
        # ملاحظات
        if titles.notes:
            parts.append("---")
            parts.append("")
            parts.append("## 📌 ملاحظات إضافية")
            parts.append("")
            parts.append(titles.notes)
            parts.append("")
        
        # كتابة الملف
        content = "\n".join(parts)
        filepath.write_text(content, encoding="utf-8")
        
        return filepath