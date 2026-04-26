from __future__ import annotations

import re
from typing import List, Optional, ClassVar

from config.constants import CAUSE_DEP
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class MissingDependenciesDetector(Detector):
    _RE_DETAIL: ClassVar[re.Pattern[str]] = re.compile(
        r"Mod ID:\s*'(?P<mod>[^']+)'\s*,\s*Requested by:\s*'(?P<req>[^']+)'\s*,\s*Expected range:\s*'(?P<range>[^']*)'\s*,\s*Actual version:\s*'(?P<actual>[^']*)'",
        flags=re.IGNORECASE,
    )
    _RE_RANGE: ClassVar[re.Pattern[str]] = re.compile(r"^\s*([\[\(])\s*([^,]*?)\s*,\s*([^\)\]]*?)\s*([\)\]])\s*$")
    _RE_MISSING: ClassVar[re.Pattern[str]] = re.compile(
        r"(?:missing\s+(?:mod\s+)?['\"]?([A-Za-z0-9_.\-]+)['\"]?(?:\s+(?:mod|dependency))?|"
        r"requires\s+(?:mod\s+)?['\"]?([A-Za-z0-9_.\-]+)['\"]?|"
        r"missing or unsupported mandatory dependencies:?\s*['\"]?([A-Za-z0-9_.\-]+)?['\"]?)",
        flags=re.IGNORECASE,
    )
    _RE_MOD_ID: ClassVar[re.Pattern[str]] = re.compile(r"Mod ID:\s*'([^']+)'", flags=re.IGNORECASE)
    _RE_CLEAN_INVALID: ClassVar[re.Pattern[str]] = re.compile(r"[^\w\.\-]")
    _RE_CLEAN_LEADING: ClassVar[re.Pattern[str]] = re.compile(r"^[0-9\-_]+")
    _RE_HAS_ALPHA: ClassVar[re.Pattern[str]] = re.compile(r"[A-Za-z]")
    
    CONFLICT_INDICATORS: ClassVar[tuple[str, ...]] = (
        "is incompatible with",
        "incompatible mod versions",
        "version conflict",
        "version mismatch",
    )
    MISSING_INDICATORS: ClassVar[tuple[str, ...]] = (
        "missing or unsupported mandatory dependencies",
        "missing mod",
        "missing dependency",
        "requires mod",
        "mod id:",
    )
    INVALID_NAMES: ClassVar[frozenset[str]] = frozenset({
        "mods.toml", "sound", "or", "file", "id", "state", "from", 
        "dependency", "class", "signature", "jar", "json", "mod"
    })

    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        txt = crash_log or ""
        found = []

        lower_txt = txt.lower()
        has_conflict_only = any(ind in lower_txt for ind in self.CONFLICT_INDICATORS)
        has_missing_indicator = any(ind in lower_txt for ind in self.MISSING_INDICATORS)
        
        if has_conflict_only and not has_missing_indicator:
            return context.results

        for m in self._RE_DETAIL.finditer(txt):
            mod = m.group("mod").strip()
            req = m.group("req").strip()
            rang = m.group("range").strip()
            actual = m.group("actual").strip()

            comp = self._range_to_comparator(rang)
            if not comp:
                comp = rang or "版本范围未知"

            line = f"{req}（MOD）需要 {mod}（前置）{comp}"
            if actual and actual.upper() != "[MISSING]":
                line += f"，实际版本: {actual}"
            found.append(line)

        if found:
            items_to_add = []
            seen = set()
            for l in found:
                if l not in seen:
                    items_to_add.append("  - " + l)
                    seen.add(l)
            context.add_result_block(
                "检测到可能的缺失依赖（详尽解析）:",
                items_to_add,
                detector=self.get_name(),
                cause_label=CAUSE_DEP
            )
            return context.results

        missing = set()

        for m in self._RE_MISSING.finditer(txt):
            groups = [g for g in m.groups() if g]
            for cand_str in groups:
                cand = self._is_valid_modname(cand_str)
                if cand:
                    missing.add(cand)

        for m in self._RE_MOD_ID.finditer(txt):
            start = max(0, m.start() - 100)
            end = min(len(txt), m.end() + 50)
            context_area = txt[start:end].lower()
            if "missing" in context_area or "required" in context_area or "need" in context_area or "requested by" in context_area:
                cand = self._is_valid_modname(m.group(1))
                if cand:
                    missing.add(cand)

        if missing:
            items_to_add = [f"  - {mod}" for mod in sorted(missing)]
            context.add_result_block(
                "检测到可能的缺失依赖的MOD:",
                items_to_add,
                detector=self.get_name(),
                cause_label=CAUSE_DEP
            )
        return context.results

    @classmethod
    def _range_to_comparator(cls, rng: str) -> str:
        rng = rng.strip()
        m = cls._RE_RANGE.match(rng)
        if not m:
            return rng or ""
        lb_incl = m.group(1) == "["
        lb = m.group(2).strip()
        ub = m.group(3).strip()
        ub_incl = m.group(4) == "]"
        parts = []
        if lb:
            op = ">=" if lb_incl else ">"
            parts.append(f"{op}{lb}")
        if ub:
            op = "<=" if ub_incl else "<"
            parts.append(f"{op}{ub}")
        return " and ".join(parts)

    @classmethod
    def _is_valid_modname(cls, s: str) -> Optional[str]:
        s2 = cls._RE_CLEAN_INVALID.sub("", s or "")
        s2 = cls._RE_CLEAN_LEADING.sub("", s2)
        if not s2 or not cls._RE_HAS_ALPHA.search(s2):
            return None
        low = s2.lower()
        if low in cls.INVALID_NAMES:
            return None
        if len(low) < 2:
            return None
        if s2.isupper() and len(s2) <= 10:
            return None
        return s2

    def get_name(self) -> str:
        return "DependencyDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_DEP
