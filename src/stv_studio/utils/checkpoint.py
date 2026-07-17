"""
Checkpoint Manager - حفظ تدريجي لكل خطوة بالـ Pipeline
==========================================================
يحفظ نتيجة كل خطوة فور نجاحها، عشان لو فشلت خطوة لاحقة،
تبقى نتائج الخطوات الناجحة محفوظة ولا تُفقد.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from stv_studio.config import PROJECT_ROOT


class CheckpointManager:
    """
    يدير ملف checkpoint واحد لكل تشغيل، يُحدَّث بعد كل خطوة ناجحة.

    الاستخدام:
        cp = CheckpointManager()
        cp.save_step("analysis", analysis.model_dump())
        cp.save_step("titles", titles_result.model_dump())
        ...
        cp.mark_complete()
    """

    CHECKPOINT_DIR = PROJECT_ROOT / "outputs" / "checkpoints"

    def __init__(self, run_id: Optional[str] = None):
        self.run_id = run_id or datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        self.filepath = self.CHECKPOINT_DIR / f"checkpoint_{self.run_id}.json"
        self._data: dict[str, Any] = {
            "run_id": self.run_id,
            "started_at": datetime.now().isoformat(),
            "status": "running",
            "steps_completed": [],
            "data": {},
            "cost_so_far_usd": 0.0,
        }
        self._write()

    def save_step(self, step_name: str, step_data: dict, cost_so_far: float = 0.0) -> None:
        """يحفظ نتيجة خطوة ناجحة فوراً."""
        self._data["data"][step_name] = step_data
        if step_name not in self._data["steps_completed"]:
            self._data["steps_completed"].append(step_name)
        self._data["cost_so_far_usd"] = cost_so_far
        self._data["last_updated"] = datetime.now().isoformat()
        self._write()
        print(f"[CHECKPOINT] Saved step '{step_name}' -> {self.filepath.name}")

    def mark_failed(self, step_name: str, error: str) -> None:
        """يسجّل فشل خطوة معينة مع سبب الخطأ."""
        self._data["status"] = "failed"
        self._data["failed_at_step"] = step_name
        self._data["error"] = error
        self._data["failed_at"] = datetime.now().isoformat()
        self._write()
        print(f"[CHECKPOINT] Marked as FAILED at step '{step_name}' -> {self.filepath.name}")

    def mark_complete(self) -> None:
        """يسجّل نجاح كامل الـ Pipeline."""
        self._data["status"] = "complete"
        self._data["completed_at"] = datetime.now().isoformat()
        self._write()

    def _write(self) -> None:
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    @classmethod
    def list_incomplete(cls) -> list[Path]:
        """يرجع كل ملفات checkpoint غير المكتملة (status != complete)."""
        if not cls.CHECKPOINT_DIR.exists():
            return []
        incomplete = []
        for f in sorted(cls.CHECKPOINT_DIR.glob("checkpoint_*.json")):
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            if data.get("status") != "complete":
                incomplete.append(f)
        return incomplete
