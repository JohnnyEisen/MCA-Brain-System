from __future__ import annotations

from typing import List, Optional

from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class ModConflictsDetector(Detector):
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        txt = (crash_log or "").lower()
        if "conflict" in txt or "incompatible" in txt or "failed to load mod" in txt:
            lines = []
            for line in txt.splitlines():
                if "conflict" in line or "incompatible" in line or "failed to load mod" in line:
                    lines.append(line.strip()[:300])
            if lines:
                context.add_result("日志中存在冲突或不兼容提示（摘录）:", detector=self.get_name())
                for l in lines[:10]:
                    context.add_result("  - " + l, detector=self.get_name())
        return context.results

    def get_name(self) -> str:
        return "ModConflictsDetector"

    def get_cause_label(self) -> Optional[str]:
        return None
