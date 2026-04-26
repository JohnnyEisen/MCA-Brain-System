from __future__ import annotations

import re
from typing import List, Optional, ClassVar

from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class MissingGeckoLibDetector(Detector):
    _RE_GECKOLIB: ClassVar[re.Pattern[str]] = re.compile(
        r"software\.bernie\.geckolib", re.IGNORECASE
    )
    _RE_MOD_INSTANCE: ClassVar[re.Pattern[str]] = re.compile(
        r"Failed to create mod instance\.\s*ModID:\s*([A-Za-z0-9_\-]+)",
        re.IGNORECASE
    )

    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        analyzer = context.analyzer
        analyzer.geckolib_missing_mods = []
        if not self._RE_GECKOLIB.search(crash_log or ""):
            return context.results
        ids = set()
        for m in self._RE_MOD_INSTANCE.finditer(crash_log):
            ids.add(m.group(1))
        if not ids:
            for modid in analyzer.mods.keys():
                if "zombie" in modid.lower():
                    ids.add(modid)
        analyzer.geckolib_missing_mods = sorted(ids)
        return context.results

    def get_name(self) -> str:
        return "GeckoLibDetector"

    def get_cause_label(self) -> Optional[str]:
        return None
