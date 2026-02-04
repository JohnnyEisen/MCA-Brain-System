from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass
class AnalysisEvent:
    type: str
    payload: Dict[str, Any]


class EventTypes:
    ANALYSIS_START = "analysis_start"
    ANALYSIS_PROGRESS = "analysis_progress"
    DETECTOR_COMPLETE = "detector_complete"
    UI_UPDATE = "ui_update"
    ANALYSIS_COMPLETE = "analysis_complete"
    ANALYSIS_ERROR = "analysis_error"


class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[Callable[[AnalysisEvent], None]]] = {}

    def subscribe(self, event_type: str, handler: Callable[[AnalysisEvent], None]) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    def unsubscribe(self, event_type: str, handler: Callable[[AnalysisEvent], None]) -> None:
        if event_type in self._subscribers:
            self._subscribers[event_type] = [h for h in self._subscribers[event_type] if h != handler]

    def publish(self, event: AnalysisEvent) -> None:
        for handler in self._subscribers.get(event.type, []):
            try:
                handler(event)
            except Exception:
                continue
