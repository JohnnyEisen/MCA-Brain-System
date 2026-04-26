"""Mixin Conflict Detector.

Detects Mixin related errors and conflicts.
"""
from __future__ import annotations

import re
from typing import List, Optional

from config.constants import CAUSE_OTHER
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class MixinConflictsDetector(Detector):
    """Detect Mixin configuration errors, injection failures, compatibility issues."""
    
    # Precompiled patterns for performance
    _ERROR_PATTERNS = None
    _WARNING_PATTERNS = None
    _MIXIN_NAME_PATTERN = re.compile(r"mixins?[\._][\w\.]+", re.IGNORECASE)
    _INVALID_INJECTION_PATTERN = re.compile(r"InvalidInjectionException", re.IGNORECASE)
    _INVALID_DESCRIPTOR_PATTERN = re.compile(
        r"Invalid descriptor on\s+([^:\n]+):([^\s\n]+)",
        re.IGNORECASE
    )
    
    @classmethod
    def _get_error_patterns(cls) -> List[re.Pattern]:
        if cls._ERROR_PATTERNS is None:
            patterns = [
                r"Mixin\s+(apply\s+)?failed",
                r"Invalid\s+Mixin\s+configuration",
                r"InvalidInjectionException",
                r"Invalid\s+descriptor\s+on",
                r"Mixin\s+transformation\s+error",
                r"MixinApplyError",
                r"MixinTransformerError",
                r"Critical\s+injection\s+failure",
                r"Compatibility\s+error\s+in\s+Mixin",
                r"Found\s+incompatible\s+mixin\s+configuration",
                r"Mixin\s+.*\s+could\s+not\s+be\s+applied",
            ]
            cls._ERROR_PATTERNS = [re.compile(p, re.IGNORECASE) for p in patterns]
        return cls._ERROR_PATTERNS
    
    @classmethod
    def _get_warning_patterns(cls) -> List[re.Pattern]:
        if cls._WARNING_PATTERNS is None:
            patterns = [
                r"Mixin\s+.*\s+conflict",
                r"Mixin\s+.*\s+error",
                r"@Inject.*failed",
                r"@Redirect.*failed",
                r"target\s+method\s+not\s+found",
            ]
            cls._WARNING_PATTERNS = [re.compile(p, re.IGNORECASE) for p in patterns]
        return cls._WARNING_PATTERNS
    
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        txt = crash_log or ""

        # 强信号优先：InvalidInjectionException + Invalid descriptor on
        has_invalid_injection = bool(self._INVALID_INJECTION_PATTERN.search(txt))
        descriptor_match = self._INVALID_DESCRIPTOR_PATTERN.search(txt)
        if has_invalid_injection:
            context.add_result(
                "Detected InvalidInjectionException: Mixin descriptor does not match target method signature.",
                detector=self.get_name(),
                cause_label=CAUSE_OTHER,
            )

            if descriptor_match:
                context.add_result(
                    f"  Faulty Mixin: {descriptor_match.group(1)}:{descriptor_match.group(2)}",
                    detector=self.get_name(),
                )
            else:
                line_match = re.search(r"^.*Invalid descriptor on.*$", txt, flags=re.IGNORECASE | re.MULTILINE)
                if line_match:
                    context.add_result(
                        f"  Evidence: {line_match.group(0).strip()}",
                        detector=self.get_name(),
                    )

            context.add_result(
                "Suggestion: Update/remove the mod providing this mixin, or use a build matching Minecraft and Loader versions.",
                detector=self.get_name(),
            )
            return context.results
        
        # Collect error signals
        error_matches = []
        for pattern in self._get_error_patterns():
            if pattern.search(txt):
                error_matches.append(pattern.pattern)
        
        # Collect warning signals
        warning_matches = []
        for pattern in self._get_warning_patterns():
            if pattern.search(txt):
                warning_matches.append(pattern.pattern)
        
        # Report if error found, or multiple warnings
        if error_matches:
            context.add_result(
                "Detected Mixin error: configuration or injection failure may cause crash.",
                detector=self.get_name(),
                cause_label=CAUSE_OTHER
            )
            mixin_names = self._MIXIN_NAME_PATTERN.findall(txt)
            unique_mixins = list(set(mixin_names))[:5]
            if unique_mixins:
                context.add_result(
                    f"  Related Mixins: {', '.join(unique_mixins)}",
                    detector=self.get_name()
                )
            context.add_result(
                "Suggestion: Check conflicting mods, try removing or updating; check Mixin config compatibility.",
                detector=self.get_name()
            )
        elif len(warning_matches) >= 2:
            context.add_result(
                "Detected potential Mixin compatibility issue.",
                detector=self.get_name(),
                cause_label=CAUSE_OTHER
            )
        
        return context.results

    def get_name(self) -> str:
        return "MixinConflictsDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_OTHER
