from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional

from config.constants import CAUSE_DUP
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class DuplicateModsDetector(Detector):
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        """
        检测日志中可能的重复 JAR / MOD，并过滤常见核心库以避免误报。
        结果会以 "可能的重复MOD/JAR:" 加入 analyzer.analysis_results（若有）。
        """
        analyzer = context.analyzer
        IGNORE_PREFIXES = {
            "fmlcore", "client", "authlib", "fmlloader", "modlauncher",
            "bootstraplauncher", "forge", "minecraft", "netty", "libraries",
            "javafmllanguage", "securejarhandler", "lowcodelanguage", "mclanguage"
        }
        IGNORE_KEYWORDS = ("loader", "launcher", "bootstrap", "authlib", "client", "fml", "forge")

        duplicates = []
        jar_matches = re.findall(r"([A-Za-z0-9_\-]+-[0-9][A-Za-z0-9\.\-_]+)\.jar", crash_log)
        jar_counts = Counter(jar_matches)
        for jar, count in jar_counts.items():
            lowjar = jar.lower()
            base = lowjar.split("-", 1)[0]
            if base in IGNORE_PREFIXES:
                continue
            if any(k in lowjar for k in IGNORE_KEYWORDS):
                continue
            if count > 1:
                duplicates.append(f"{jar}.jar 出现次数: {count}")

        for modid, vers in analyzer.mods.items():
            if not modid:
                continue
            low = modid.lower()
            if any(low.startswith(p) for p in IGNORE_PREFIXES):
                continue
            occurrences = len(re.findall(rf"{re.escape(modid)}-[0-9][A-Za-z0-9\.\-_]+\.jar", crash_log, flags=re.IGNORECASE))
            if occurrences > 1:
                desc = f"{modid}*.jar 似乎出现次数: {occurrences}"
                if desc not in duplicates:
                    duplicates.append(desc)

        if duplicates:
            unique_dups = list(dict.fromkeys(duplicates))
            MAX_DISPLAY = 10
            items_to_add = []

            if len(unique_dups) > MAX_DISPLAY:
                items_to_add.extend(["  - " + d for d in unique_dups[:MAX_DISPLAY]])
                items_to_add.append(f"  ... (以及其他 {len(unique_dups) - MAX_DISPLAY} 个重复项，请查看完整日志)")
            else:
                items_to_add.extend(["  - " + d for d in unique_dups])

            context.add_result_block(
                "可能的重复MOD/JAR:",
                items_to_add,
                detector=self.get_name(),
                cause_label=CAUSE_DUP
            )
        return context.results

    def get_name(self) -> str:
        return "DuplicateModsDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_DUP
