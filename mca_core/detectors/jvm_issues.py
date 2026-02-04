from __future__ import annotations

from typing import List, Optional

from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class JvmIssuesDetector(Detector):
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        txt = crash_log or ""
        issues = []
        if "NoClassDefFoundError" in txt or "ClassNotFoundException" in txt:
            issues.append("缺少类（NoClassDefFoundError/ClassNotFoundException）可能是Mod或版本不匹配导致。")
        if "unsupported class file major version" in txt.lower():
            issues.append("JVM版本不兼容（class file major version）。请检查Java版本。")
        for msg in issues:
            context.add_result(msg, detector=self.get_name())
        return context.results

    def get_name(self) -> str:
        return "JvmIssuesDetector"

    def get_cause_label(self) -> Optional[str]:
        return None
