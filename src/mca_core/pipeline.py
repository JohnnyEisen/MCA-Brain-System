from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Protocol


class AnalysisStep(Protocol):
    def should_execute(self, context) -> bool:
        ...

    def execute(self, crash_log: str, context):
        ...


@dataclass
class AnalysisResult:
    entries: List[str] = field(default_factory=list)

    def merge(self, other: "AnalysisResult") -> None:
        self.entries.extend(other.entries)


class ConfigurableAnalysisPipeline:
    def __init__(self, steps: List[AnalysisStep]):
        self.steps = steps

    def execute(self, crash_log: str, context) -> AnalysisResult:
        result = AnalysisResult()
        for step in self.steps:
            if not step.should_execute(context):
                continue
            step_result = step.execute(crash_log, context)
            if isinstance(step_result, AnalysisResult):
                result.merge(step_result)
        return result
