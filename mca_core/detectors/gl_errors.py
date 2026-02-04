from __future__ import annotations

from typing import List, Optional

from config.constants import CAUSE_GPU
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class GlErrorsDetector(Detector):
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        analyzer = context.analyzer
        txt = crash_log or ""
        lower = txt.lower()

        keyword_map = [
            ("glfw", "GLFW"),
            ("opengl", "OpenGL"),
            ("gl error", "GL Error"),
            ("opengl error", "OpenGL Error"),
            ("shader", "shader"),
        ]
        found = []
        for key, label in keyword_map:
            if key in lower:
                found.append(label)

        if not found:
            return context.results

        uniq = sorted(set(found))
        context.add_result("检测到可能的 GPU/驱动/GL 错误（OpenGL/GLFW/Shader 相关）:", detector=self.get_name(), cause_label=CAUSE_GPU)
        context.add_result("  - 关键字: " + ", ".join(uniq), detector=self.get_name())

        snippets = []
        for line in txt.splitlines():
            l = line.lower()
            if any(k in l for k, _ in keyword_map):
                snippets.append(line.strip())
                if len(snippets) >= 10:
                    break
        analyzer.gl_snippets = snippets

        try:
            if not analyzer.gpu_info and hasattr(analyzer, "_collect_system_info"):
                info = analyzer._collect_system_info() or {}
                analyzer.gpu_info = info.get("gpus") or {}
        except Exception:
            pass

        render_mods = [
            m for m in analyzer.mods.keys()
            if any(x in m.lower() for x in ("iris", "sodium", "optifine", "indium", "indigo"))
        ]
        if render_mods:
            context.add_result("  - 可能涉及的渲染/光影 MOD: " + ", ".join(render_mods), detector=self.get_name())

        context.add_result(
            "建议: 更新显卡驱动；尝试禁用光影/着色器或移除相关渲染MOD（Iris/OptiFine/Sodium/Iris 的替代 Indium/Indigo）；如果是 Windows，尝试安装最新的 GPU 驱动并切换到默认渲染器以排查。"
        , detector=self.get_name())
        context.add_result("详情: 查看日志中含 'GLFW' / 'OpenGL' / 'shader' 的栈和错误行以获得更多线索。", detector=self.get_name())

        try:
            rules = (analyzer.gpu_issues or {}).get("rules", [])
            txt_full = (analyzer.crash_log or "").lower()
            for rule in rules:
                for token in rule.get("match", []):
                    if token.lower() in txt_full:
                        advice = rule.get("advice")
                        if advice:
                            context.add_result(f"针对 {rule.get('vendor', 'GPU')} 的建议: {advice}", detector=self.get_name())
                        break
        except Exception:
            pass
        return context.results

    def get_name(self) -> str:
        return "GPUDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_GPU
