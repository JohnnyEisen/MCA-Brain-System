from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict


@dataclass
class DetectionResult:
    message: str
    detector: str
    cause_label: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisContext:
    analyzer: Any
    crash_log: str
    results: List[DetectionResult] = field(default_factory=list)
    cause_counts: Dict[str, int] = field(default_factory=dict)

    def _add_result_internal(self, message: str, detector: str, cause_label: Optional[str], metadata: Dict[str, Any]) -> DetectionResult:
        """Internal helper to add result without locking (caller must hold lock)."""
        if self.analyzer and message:
            self.analyzer.analysis_results.append(message)
            if hasattr(self.analyzer, "_auto_test_write_log"):
                    try: self.analyzer._auto_test_write_log(f"DEBUG: add_result matches: {detector} -> {cause_label}")
                    except: pass
        
        if self.analyzer and cause_label:
            try:
                if hasattr(self.analyzer, "add_cause"):
                    self.analyzer.add_cause(cause_label)
                elif hasattr(self.analyzer, "_add_cause"):
                    self.analyzer._add_cause(cause_label)
            except Exception:
                pass
        
        if cause_label:
            self.cause_counts[cause_label] = self.cause_counts.get(cause_label, 0) + 1

        res = DetectionResult(message=message, detector=detector, cause_label=cause_label, metadata=metadata or {})
        self.results.append(res)
        return res

    def add_result(self, message: str, detector: str, cause_label: Optional[str] = None, **metadata) -> DetectionResult:
        lock = getattr(self.analyzer, "lock", None)
        if lock:
            with lock:
                return self._add_result_internal(message, detector, cause_label, metadata)
        else:
            return self._add_result_internal(message, detector, cause_label, metadata)

    def add_result_block(self, header: str, items: List[str], detector: str, cause_label: Optional[str] = None):
        """
        Atomically add a block of results (Header + Items) to ensure they stay contiguous
        in the output, preventing interleaving with other detectors.
        """
        lock = getattr(self.analyzer, "lock", None)

        def _do_work():
            self._add_result_internal(header, detector, cause_label, {})
            for item in items:
                try:
                    self._add_result_internal(item, detector, None, {})
                except Exception:
                    pass

        if lock:
            with lock:
                _do_work()
        else:
            _do_work()
