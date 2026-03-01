from __future__ import annotations

import re
from typing import List, Optional

from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class MissingGeckoLibDetector(Detector):
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        """检测 GeckoLib 缺失导致的 mod 初始化失败（只记录到属性，由摘要统一输出）。"""
        analyzer = context.analyzer
        analyzer.geckolib_missing_mods = []
        if "software.bernie.geckolib" not in (crash_log or ""):
            return context.results
        ids = set()
        for m in re.finditer(
            r"Failed to create mod instance\.\s*ModID:\s*([A-Za-z0-9_\-]+)",
            crash_log,
            flags=re.IGNORECASE,
        ):
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
