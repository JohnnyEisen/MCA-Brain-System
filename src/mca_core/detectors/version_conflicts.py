"""Version Conflict Detector.

Detects mod version conflicts and duplicate mods.
"""
from __future__ import annotations

import re
from typing import List, Optional

from config.constants import CAUSE_VER
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class VersionConflictsDetector(Detector):
    """Detect version conflicts (strict mode: only detect explicit conflict text)."""
    
    # Precompiled patterns for performance
    _COMPILED_PATTERNS = None
    
    @classmethod
    def _get_patterns(cls) -> List[re.Pattern]:
        if cls._COMPILED_PATTERNS is None:
            patterns = [
                r"is\s+incompatible\s+with\s+loaded\s+version",
                r"version\s+mismatch",
                r"duplicate\s+mod\s+found",
                r"found\s+mod\s+file.*conflict",
                r"incompatible\s+mod",
                r"mod\s+resolution\s+failed",
                r"dependency\s+requirements\s+not\s+met",
            ]
            cls._COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in patterns]
        return cls._COMPILED_PATTERNS
    
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        analyzer = context.analyzer
        txt = crash_log or ""
        lower = txt.lower()
        
        conflicts = []
        
        # Detect version conflict signals using precompiled patterns
        for pattern in self._get_patterns():
            if pattern.search(lower):
                conflicts.append(pattern.pattern.replace(r"\s+", " ").replace(r".*", "..."))
        
        # Output results (strict mode: must have explicit conflict text)
        if conflicts:
            context.add_result(
                "Detected version conflict or incompatibility:",
                detector=self.get_name(),
                cause_label=CAUSE_VER
            )
            
            unique_conflicts = list(set(conflicts))[:5]
            context.add_result(
                "  - Conflict types: " + ", ".join(unique_conflicts),
                detector=self.get_name()
            )
            
            context.add_result(
                "Suggestion: Remove conflicting mod versions; check if mods are compatible with current Minecraft version.",
                detector=self.get_name()
            )
        
        return context.results

    def get_name(self) -> str:
        return "VersionConflictDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_VER
