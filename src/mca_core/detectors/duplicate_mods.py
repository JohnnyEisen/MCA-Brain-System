"""Duplicate MOD Detector.

Detects duplicate JAR files or MODs in log (strict mode, reduce false positives).
"""
from __future__ import annotations

import re
from collections import Counter
from typing import List, Optional

from config.constants import CAUSE_DUP
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class DuplicateModsDetector(Detector):
    """Detect duplicate MOD/JAR (strict mode: must appear multiple times)."""
    
    # Ignore prefixes (core libraries, allowed to repeat)
    IGNORE_PREFIXES = {
        "fmlcore", "client", "authlib", "fmlloader", "modlauncher",
        "bootstraplauncher", "forge", "minecraft", "netty", "libraries",
        "javafmllanguage", "securejarhandler", "lowcodelanguage", "mclanguage",
        "java", "jdk", "lwjgl", "jopt", "gson", "guava", "commons",
        "log4j", "slf4j", "jline", "jna", "oshi", "mixin", "spongepowered",
    }
    
    # Ignore keywords
    IGNORE_KEYWORDS = ("loader", "launcher", "bootstrap", "authlib", "client", 
                       "fml", "forge", "library", "libraries", "core")
    
    # Precompiled pattern for performance
    _JAR_PATTERN = re.compile(r"([A-Za-z0-9_\-]+-[0-9][A-Za-z0-9\.\-_]+)\.jar", re.IGNORECASE)
    
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        """Detect possible duplicate JAR / MOD in log."""
        analyzer = context.analyzer
        
        duplicates = []
        
        # Match all .jar file references using precompiled pattern
        jar_matches = self._JAR_PATTERN.findall(crash_log)
        jar_counts = Counter(jar_matches)
        
        for jar, count in jar_counts.items():
            lowjar = jar.lower()
            base = lowjar.split("-", 1)[0]
            
            # Filter core libraries
            if base in self.IGNORE_PREFIXES:
                continue
            if any(k in lowjar for k in self.IGNORE_KEYWORDS):
                continue
            
            # Only report if appears 15+ times
            if count >= 15:
                duplicates.append(f"{jar}.jar appears {count} times")
        
        # Detect from analyzer.mods
        for modid, vers in analyzer.mods.items():
            if not modid:
                continue
            low = modid.lower()
            if any(low.startswith(p) for p in self.IGNORE_PREFIXES):
                continue
            
            pattern = re.compile(rf"{re.escape(modid)}-[0-9][A-Za-z0-9\.\-_]+\.jar", re.IGNORECASE)
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
