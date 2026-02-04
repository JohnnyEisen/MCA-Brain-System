from __future__ import annotations

import re
from typing import List, Optional

from config.constants import CAUSE_GECKO
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class GeckoLibMoreDetector(Detector):
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        """扩展识别 GeckoLib 相关错误并输出建议。"""
        analyzer = context.analyzer
        txt = crash_log or ""
        found = set(getattr(analyzer, "geckolib_missing_mods", []) or [])

        for _ in re.finditer(r"(software\.bernie\.geckolib|software/bernie/geckolib)", txt, flags=re.IGNORECASE):
            found.add("GeckoLib")

        for m in re.finditer(
            r"Failed to create mod instance\.[\s\S]{0,120}?ModID:\s*([A-Za-z0-9_\-]+)",
            txt,
            flags=re.IGNORECASE,
        ):
            found.add(m.group(1))

        if found:
            analyzer.geckolib_missing_mods = sorted(found)
            context.add_result("检测到 GeckoLib 相关的初始化失败/缺失（扩展识别）：", detector=self.get_name(), cause_label=CAUSE_GECKO)
            context.add_result("  - 可能受影响的 MOD: " + ", ".join(analyzer.geckolib_missing_mods), detector=self.get_name())
            context.add_result("  - 建议: 安装/更新 GeckoLib (software.bernie.geckolib) 或移除相关 MOD 以排查", detector=self.get_name())
        return context.results

    def get_name(self) -> str:
        return "GeckoLibDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_GECKO
