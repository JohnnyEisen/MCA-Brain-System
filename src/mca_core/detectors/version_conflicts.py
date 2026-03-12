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
    
    PRIORITY_HIGH = 10  # 较高优先级，在缺失依赖检测之前运行
    
    # Precompiled patterns for performance
    _COMPILED_PATTERNS = None
    _CONFLICT_DETAIL_PATTERNS = None
    
    @classmethod
    def _get_patterns(cls) -> List[re.Pattern]:
        if cls._COMPILED_PATTERNS is None:
            patterns = [
                r"is\s+incompatible\s+with",
                r"incompatible\s+mod\s+versions",
                r"version\s+conflict",
                r"version\s+mismatch",
                r"duplicate\s+mod\s+found",
                r"found\s+mod\s+file.*conflict",
                r"incompatible\s+mod",
                r"mod\s+resolution\s+failed",
                r"dependency\s+requirements\s+not\s+met",
                r"but\s+version\s+.*\s+is\s+required\s+by",
                r"is\s+incompatible\s+with\s+mod",
            ]
            cls._COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in patterns]
        return cls._COMPILED_PATTERNS
    
    @classmethod
    def _get_detail_patterns(cls) -> List[re.Pattern]:
        """Patterns that extract specific conflict details."""
        if cls._CONFLICT_DETAIL_PATTERNS is None:
            cls._CONFLICT_DETAIL_PATTERNS = [
                # "mod A is incompatible with mod B"
                re.compile(r"([A-Za-z0-9_\-]+)\s+is\s+incompatible\s+with\s+([A-Za-z0-9_\-]+)", re.IGNORECASE),
                # "but version X is required by mod Y"
                re.compile(r"but\s+version\s+([0-9.]+)\s+is\s+required\s+by\s+([A-Za-z0-9_\-]+)", re.IGNORECASE),
                # "found mod file /path/modA-X.jar of version X"
                re.compile(r"found\s+mod\s+file\s+.*?([A-Za-z0-9_\-]+)[\-\d.]*\.jar\s+of\s+version\s+([0-9.]+)", re.IGNORECASE),
            ]
        return cls._CONFLICT_DETAIL_PATTERNS
    
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        analyzer = context.analyzer
        txt = crash_log or ""
        lower = txt.lower()
        
        conflicts = []
        conflict_details = []
        
        # Detect version conflict signals using precompiled patterns
        for pattern in self._get_patterns():
            if pattern.search(lower):
                conflicts.append(pattern.pattern.replace(r"\s+", " ").replace(r".*", "..."))
        
        # Extract specific conflict details
        for pattern in self._get_detail_patterns():
            for m in pattern.finditer(txt):
                groups = [g for g in m.groups() if g]
                if groups:
                    conflict_details.append(" - ".join(groups))
        
        # Output results (strict mode: must have explicit conflict text)
        if conflicts:
            context.add_result(
                "检测到版本冲突或不兼容:",
                detector=self.get_name(),
                cause_label=CAUSE_VER
            )
            
            if conflict_details:
                unique_details = list(set(conflict_details))[:5]
                for detail in unique_details:
                    context.add_result(
                        f"  - 冲突详情: {detail}",
                        detector=self.get_name()
                    )
            
            unique_conflicts = list(set(conflicts))[:5]
            context.add_result(
                "  - 冲突类型: " + ", ".join(unique_conflicts),
                detector=self.get_name()
            )
            
            context.add_result(
                "建议: 移除冲突的模组版本；检查模组是否与当前 Minecraft 版本兼容。",
                detector=self.get_name()
            )
        
        return context.results

    def get_name(self) -> str:
        return "VersionConflictDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_VER
    
    def get_priority(self) -> int:
        return self.PRIORITY_HIGH
