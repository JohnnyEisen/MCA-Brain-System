from __future__ import annotations

from typing import List, Optional

from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class LoaderDetector(Detector):
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        analyzer = context.analyzer
        txt = (crash_log or "").lower()
        if "forge" in txt and "fml" in txt:
            analyzer.loader_type = "Forge"
        elif "fabric loader" in txt or "fabric" in txt:
            analyzer.loader_type = "Fabric"
        else:
            analyzer.loader_type = None
        return context.results

    def get_name(self) -> str:
        return "LoaderDetector"

    def get_cause_label(self) -> Optional[str]:
        return None
