from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional

from .contracts import AnalysisContext, DetectionResult


class Detector(ABC):
    """Unified detector interface with priority support."""

    PRIORITY_CRITICAL = 0
    PRIORITY_HIGH = 10
    PRIORITY_NORMAL = 50
    PRIORITY_LOW = 100

    @abstractmethod
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        """Run detection on crash_log, writing to context and returning results."""
        raise NotImplementedError

    @abstractmethod
    def get_name(self) -> str:
        """Human-readable detector name."""
        raise NotImplementedError

    @abstractmethod
    def get_cause_label(self) -> Optional[str]:
        """Associated cause label for summary (if any)."""
        raise NotImplementedError

    def get_priority(self) -> int:
        """Detection priority. Lower values run first. Default: PRIORITY_NORMAL."""
        return self.PRIORITY_NORMAL

    def get_confidence(self) -> float:
        """Default confidence for results from this detector. Range: 0.0-1.0."""
        return 0.8
