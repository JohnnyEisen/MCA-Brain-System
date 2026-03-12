from __future__ import annotations

import re
from typing import List, Optional

from config.constants import CAUSE_DEP
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class MissingDependenciesDetector(Detector):
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        """
        严格检测缺失依赖：
        - 优先解析 ModSorter / ModLoadingException 中的 "Missing or unsupported mandatory dependencies" 块
          并以 "请求方（MOD）需要 前置（MOD）>=/<= 版本" 的格式加入 analysis_results。
        - 若未发现该块，再使用宽松上下文匹配作为后备。
        - 排除版本冲突场景（incompatible）避免误报。
        """
        txt = crash_log or ""
        found = []

        # 排除纯版本冲突场景（避免误报）
        lower_txt = txt.lower()
        conflict_indicators = [
            "is incompatible with",
            "incompatible mod versions",
            "version conflict",
            "version mismatch",
        ]
        has_conflict_only = any(ind in lower_txt for ind in conflict_indicators)
        
        # 如果只有冲突指示器而没有明确的缺失依赖指示器，则跳过
        missing_indicators = [
            "missing or unsupported mandatory dependencies",
            "missing mod",
            "missing dependency",
            "requires mod",
            "mod id:",
        ]
        has_missing_indicator = any(ind in lower_txt for ind in missing_indicators)
        
        if has_conflict_only and not has_missing_indicator:
            return context.results

        detail_re = re.compile(
            r"Mod ID:\s*'(?P<mod>[^']+)'\s*,\s*Requested by:\s*'(?P<req>[^']+)'\s*,\s*Expected range:\s*'(?P<range>[^']*)'\s*,\s*Actual version:\s*'(?P<actual>[^']*)'",
            flags=re.IGNORECASE,
        )
        for m in detail_re.finditer(txt):
            mod = m.group("mod").strip()
            req = m.group("req").strip()
            rang = m.group("range").strip()
            actual = m.group("actual").strip()

            def range_to_comparator(rng: str):
                rng = rng.strip()
                m2 = re.match(r"^\s*([\[\(])\s*([^,]*?)\s*,\s*([^\)\]]*?)\s*([\)\]])\s*$", rng)
                if not m2:
                    return rng or ""
                lb_incl = m2.group(1) == "["
                lb = m2.group(2).strip()
                ub = m2.group(3).strip()
                ub_incl = m2.group(4) == "]"
                parts = []
                if lb:
                    op = ">=" if lb_incl else ">"
                    parts.append(f"{op}{lb}")
                if ub:
                    op = "<=" if ub_incl else "<"
                    parts.append(f"{op}{ub}")
                return " and ".join(parts)

            comp = range_to_comparator(rang)
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

        def _is_valid_modname(s):
            s2 = re.sub(r"[^\w\.\-]", "", s or "")
            s2 = re.sub(r"^[0-9\-_]+", "", s2)
            if not s2 or not re.search(r"[A-Za-z]", s2):
                return None
            low = s2.lower()
            if low in {"mods.toml", "sound", "or", "file", "id", "state", "from", "dependency", "class", "signature", "jar", "json", "mod"}:
                return None
            if len(low) < 2:
                return None
            if s2.isupper() and len(s2) <= 10:
                return None
            return s2

        # 更严格的模式：必须有明确的缺失依赖上下文
        pattern = re.compile(
            r"(?:missing\s+(?:mod|dependency)|requires\s+(?:mod\s+)?([A-Za-z0-9_.\-]+)|"
            r"missing or unsupported mandatory dependencies:)\s*([A-Za-z0-9_.\-]+)?",
            flags=re.IGNORECASE,
        )
        for m in pattern.finditer(txt):
            # 提取组
            groups = [g for g in m.groups() if g]
            for cand_str in groups:
                cand = _is_valid_modname(cand_str)
                if cand:
                    missing.add(cand)

        for m in re.finditer(r"Mod ID:\s*'([^']+)'", txt, flags=re.IGNORECASE):
            # 只有在附近有 "missing" 或 "required" 关键词时才添加
            start = max(0, m.start() - 100)
            end = min(len(txt), m.end() + 50)
            context_area = txt[start:end].lower()
            if "missing" in context_area or "required" in context_area or "need" in context_area:
                cand = _is_valid_modname(m.group(1))
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

    def get_name(self) -> str:
        return "DependencyDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_DEP
