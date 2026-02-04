from __future__ import annotations

from typing import List, Optional

from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class ShaderWorldConflictsDetector(Detector):
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        """
        使用 mod_conflicts.json 中的 blacklist/whitelist 做精确匹配输出（渲染 vs 世界类 MOD）。
        若 blacklist 命中，输出“已知不兼容”提示；若 whitelist 命中，输出“可能兼容”提示。
        """
        analyzer = context.analyzer
        txt = (crash_log or "").lower()
        present_mods = {k.lower() for k in analyzer.mods.keys()}
        db = getattr(analyzer, "conflict_db", {}) or {}
        blacklist = db.get("blacklist", [])
        whitelist = db.get("whitelist", [])

        def match_entry(entry):
            renders = entry.get("render", []) or []
            worlds = entry.get("world", []) or []
            render_match = any(any(r in m for m in present_mods) for r in renders) or any(r in txt for r in renders)
            world_match = any(any(w in m for m in present_mods) for w in worlds) or any(w in txt for w in worlds)
            return render_match and world_match

        found_black = [e for e in blacklist if match_entry(e)]
        found_white = [e for e in whitelist if match_entry(e)]

        if found_black:
            context.add_result("已知渲染/光影 与 世界/维度 MOD 不兼容（基于本地映射）:", detector=self.get_name())
            seen = set()
            for e in found_black:
                note = e.get("note", "")
                for r in e.get("render", []):
                    for w in e.get("world", []):
                        key = f"{r}|{w}"
                        if key in seen:
                            continue
                        seen.add(key)
                        r_display = next((m for m in analyzer.mods.keys() if r in m.lower()), r)
                        w_display = next((m for m in analyzer.mods.keys() if w in m.lower()), w)
                        context.add_result(
                            f"  - {r_display}（渲染）已知与 {w_display}（世界/维度）不兼容。{note}"
                        , detector=self.get_name())

        if found_white:
            context.add_result("已知渲染/光影 与 世界/维度 MOD 可兼容（映射提示）:", detector=self.get_name())
            seen = set()
            for e in found_white:
                note = e.get("note", "")
                for r in e.get("render", []):
                    for w in e.get("world", []):
                        key = f"{r}|{w}"
                        if key in seen:
                            continue
                        seen.add(key)
                        r_display = next((m for m in analyzer.mods.keys() if r in m.lower()), r)
                        w_display = next((m for m in analyzer.mods.keys() if w in m.lower()), w)
                        context.add_result(
                            f"  - {r_display}（渲染）与 {w_display}（世界/维度）在映射中标记为可能兼容。{note}"
                        , detector=self.get_name())

        # 若既无 blacklist 也无 whitelist 命中，方法静默返回（保留其它启发式检测）
        return context.results

    def get_name(self) -> str:
        return "ShaderWorldConflictsDetector"

    def get_cause_label(self) -> Optional[str]:
        return None
