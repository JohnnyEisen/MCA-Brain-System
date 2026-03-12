from __future__ import annotations
from dataclasses import dataclass
from typing import List


@dataclass
class DetectionRule:
    name: str
    keyword: str
    message: str

    def matches(self, crash_log: str) -> bool:
        return self.keyword.lower() in (crash_log or "").lower()

    def apply(self, crash_log: str) -> str:
        return self.message


class RuleEngine:
    def __init__(self):
        self._rules: List[DetectionRule] = []

    def add_rule(self, rule: DetectionRule):
        self._rules.append(rule)

    def evaluate(self, crash_log: str) -> List[str]:
        results = []
        for rule in self._rules:
            if rule.matches(crash_log):
                results.append(rule.apply(crash_log))
        return results
