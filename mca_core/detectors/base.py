from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Optional

from .contracts import AnalysisContext, DetectionResult


class Detector(ABC):
    """Unified detector interface."""

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
