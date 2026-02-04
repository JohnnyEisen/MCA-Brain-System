from __future__ import annotations

from typing import List, Optional

from config.constants import CAUSE_VER
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class VersionConflictsDetector(Detector):
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        analyzer = context.analyzer
        conflicts = []
        for modid, vers in analyzer.mods.items():
            normalized = set(vers)
            if len(normalized) > 1:
                conflicts.append((modid, sorted(normalized)))
        if conflicts:
            context.add_result("版本冲突(同一MOD存在多个版本)：", detector=self.get_name(), cause_label=CAUSE_VER)
            for modid, vers in conflicts:
                context.add_result(f"  - {modid}: 版本列表 -> {', '.join(vers)}", detector=self.get_name())
        return context.results

    def get_name(self) -> str:
        return "VersionConflictDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_VER
