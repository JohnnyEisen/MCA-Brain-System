from __future__ import annotations

from typing import List, Optional

from config.constants import CAUSE_MEM
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class OutOfMemoryDetector(Detector):
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        txt = (crash_log or "").lower()
        if "outofmemoryerror" in txt or "out of memory" in txt:
            context.add_result(
                "检测到：内存溢出（OutOfMemoryError）。建议：增加JVM最大堆内存（-Xmx）或检查模组引发的内存泄漏。",
                detector=self.get_name(),
                cause_label=CAUSE_MEM,
            )
        return context.results

    def get_name(self) -> str:
        return "MemoryDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_MEM
