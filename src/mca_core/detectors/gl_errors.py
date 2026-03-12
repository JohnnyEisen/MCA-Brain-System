"""GPU/OpenGL Error Detector.

Detects graphics card driver, OpenGL, and rendering related errors.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from config.constants import CAUSE_GPU
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class GlErrorsDetector(Detector):
    """Detect GPU/OpenGL/driver related errors (strict mode, filter noise)."""
    
    # Precompiled patterns for performance
    _NOISE_PATTERNS = None
    _ERROR_PATTERNS = None
    
    @classmethod
    def _get_noise_patterns(cls) -> List[re.Pattern]:
        if cls._NOISE_PATTERNS is None:
            patterns = [
                r"caught\s+exception\s+in\s+thread\s+['\"]?render",
                r"an\s+exception\s+was\s+thrown",
                r"narrator\s+library\s+not\s+available",
            ]
            cls._NOISE_PATTERNS = [re.compile(p, re.IGNORECASE) for p in patterns]
        return cls._NOISE_PATTERNS
    
    @classmethod
    def _get_error_patterns(cls) -> List[Tuple[re.Pattern, str]]:
        if cls._ERROR_PATTERNS is None:
            patterns = [
                (r"glfw\s+error\s*[\d\w]+", "GLFW Error"),
                (r"opengl\s+error\s*[\d\w]+", "OpenGL Error"),
                (r"GL_INVALID_OPERATION", "GL_INVALID_OPERATION"),
                (r"GL_INVALID_VALUE", "GL_INVALID_VALUE"),
                (r"GL_INVALID_ENUM", "GL_INVALID_ENUM"),
                (r"GL_OUT_OF_MEMORY", "GL_OUT_OF_MEMORY"),
                (r"openglexception", "OpenGLException"),
                (r"failed\s+to\s+initialize\s+opengl", "OpenGL Init Failed"),
                (r"driver\s+does\s+not\s+.*support\s+opengl", "Driver No OpenGL"),
                (r"couldn'?t\s+create\s+window", "Window Failed"),
                (r"glerror\s*\(", "GLError"),
                (r"render\s*thread\s+crashed", "RenderThread Crashed"),
                (r"tesselat.*failed", "Tessellation Failed"),
                (r"chunk\s+render.*failed", "Chunk Render Failed"),
                (r"shader\s+compil.*error", "Shader Compile Error"),
                (r"shader\s+.*failed\s+to\s+compile", "Shader Compile Failed"),
                (r"framebuffer\s+.*incomplete", "Framebuffer Incomplete"),
                (r"glsl\s+.*error", "GLSL Error"),
            ]
            cls._ERROR_PATTERNS = [(re.compile(p, re.IGNORECASE), l) for p, l in patterns]
        return cls._ERROR_PATTERNS
    
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        analyzer = context.analyzer
        txt = crash_log or ""
        lower = txt.lower()

        # Check noise patterns first
        noise_count = sum(1 for p in self._get_noise_patterns() if p.search(lower))
        
        # Collect error matches
        found = []
        for pattern, label in self._get_error_patterns():
            if pattern.search(lower):
                found.append(label)

        # No real errors, skip
        if not found:
            return context.results

        # Only noise, skip
        if noise_count > 0 and len(found) <= 1:
            weak_signals = ["RenderThread Crashed"]
            if all(f in weak_signals for f in found):
                return context.results

        uniq = sorted(set(found))
        context.add_result(
            "Detected GPU/Driver/GL error:",
            detector=self.get_name(),
            cause_label=CAUSE_GPU
        )
        context.add_result("  - Error types: " + ", ".join(uniq), detector=self.get_name())

        # Extract relevant code snippets
        snippets = []
        for line in txt.splitlines():
            l = line.lower()
            if any(p.search(l) for p, _ in self._get_error_patterns()):
                snippets.append(line.strip())
                if len(snippets) >= 10:
                    break
        if snippets:
            analyzer.gl_snippets = snippets

        # Collect GPU info
        try:
            if not analyzer.gpu_info and hasattr(analyzer, "_collect_system_info"):
                info = analyzer._collect_system_info() or {}
                analyzer.gpu_info = info.get("gpus") or {}
        except Exception:
            pass

        # Check rendering related mods
        render_mods = [
            m for m in analyzer.mods.keys()
            if any(x in m.lower() for x in ("iris", "sodium", "optifine", "indium", "indigo", "rubidium"))
        ]
        if render_mods:
            context.add_result("  - Related render/mods: " + ", ".join(render_mods), detector=self.get_name())

        context.add_result(
            "Suggestion: Update graphics driver; try disabling shaders; remove or update render mods.",
            detector=self.get_name()
        )
        
        return context.results

    def get_name(self) -> str:
        return "GPUDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_GPU
