"""Duplicate MOD Detector.

Detects duplicate JAR files or MODs in log (strict mode, reduce false positives).
"""
from __future__ import annotations

import re
from collections import Counter
from typing import ClassVar, List, Optional

from config.constants import CAUSE_DUP
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class DuplicateModsDetector(Detector):
    """Detect duplicate MOD/JAR (strict mode: must appear multiple times)."""
    
    IGNORE_PREFIXES = {
        "fmlcore", "client", "authlib", "fmlloader", "modlauncher",
        "bootstraplauncher", "forge", "minecraft", "netty", "libraries",
        "javafmllanguage", "securejarhandler", "lowcodelanguage", "mclanguage",
        "java", "jdk", "lwjgl", "jopt", "gson", "guava", "commons",
        "log4j", "slf4j", "jline", "jna", "oshi", "mixin", "spongepowered",
    }
    
    IGNORE_KEYWORDS = ("loader", "launcher", "bootstrap", "authlib", "client", 
                       "fml", "forge", "library", "libraries", "core")
    
    # 要求前缀以字母开头，避免将版本号片段误识别为 JAR 名（如 1-11.45.14.jar）
    _JAR_PATTERN = re.compile(r"([A-Za-z][A-Za-z0-9_\-]*-[0-9][A-Za-z0-9\.\-_]+)\.jar", re.IGNORECASE)
    _mod_patterns: ClassVar[dict[str, re.Pattern[str]]] = {}
    _MOD_PATTERNS_MAX = 100

    @classmethod
    def _get_mod_pattern(cls, modid: str) -> re.Pattern[str]:
        if modid in cls._mod_patterns:
            return cls._mod_patterns[modid]
        
        if len(cls._mod_patterns) >= cls._MOD_PATTERNS_MAX:
            oldest_key = next(iter(cls._mod_patterns))
            cls._mod_patterns.pop(oldest_key)
        
        pattern = re.compile(
            rf"{re.escape(modid)}-[0-9][A-Za-z0-9\.\-_]+\.jar",
            re.IGNORECASE
        )
        cls._mod_patterns[modid] = pattern
        return pattern
    
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        analyzer = context.analyzer
        
        duplicates = []
        
        jar_matches = self._JAR_PATTERN.findall(crash_log)
        jar_counts = Counter(jar_matches)
        
        for jar, count in jar_counts.items():
            lowjar = jar.lower()
            base = lowjar.split("-", 1)[0]
            
            if base in self.IGNORE_PREFIXES:
                continue
            if any(k in lowjar for k in self.IGNORE_KEYWORDS):
                continue
            
            if count >= 15:
                duplicates.append(f"{jar}.jar appears {count} times")
        
        for modid, vers in analyzer.mods.items():
            if not modid:
                continue
            low = modid.lower()
            if not re.search(r"[a-z]", low):
                continue
            if any(low.startswith(p) for p in self.IGNORE_PREFIXES):
                continue
            
            pattern = self._get_mod_pattern(modid)
            occurrences = len(pattern.findall(crash_log))
            
            if occurrences >= 15:
                desc = f"{modid}*.jar appears {occurrences} times"
                if desc not in duplicates:
                    duplicates.append(desc)
        
        if duplicates:
            unique_dups = list(dict.fromkeys(duplicates))
            MAX_DISPLAY = 5
            
            items_to_add = []
            if len(unique_dups) > MAX_DISPLAY:
                items_to_add.extend(["  - " + d for d in unique_dups[:MAX_DISPLAY]])
                items_to_add.append(f"  ... (and {len(unique_dups) - MAX_DISPLAY} more)")
            else:
                items_to_add.extend(["  - " + d for d in unique_dups])

            context.add_result_block(
                "Detected duplicate MOD/JAR:",
                items_to_add,
                detector=self.get_name(),
                cause_label=CAUSE_DUP
            )
        
        return context.results

    def get_name(self) -> str:
        return "DuplicateModsDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_DUP
