"""GPU/OpenGL Error Detector.

Detects graphics card driver, OpenGL, and rendering related errors.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Tuple

from config.constants import CAUSE_GPU
from .base import Detector
from .contracts import AnalysisContext, DetectionResult


class GlErrorsDetector(Detector):
    """Detect GPU/OpenGL/driver related errors (strict mode, filter noise)."""
    
    # Precompiled patterns for performance
    _NOISE_PATTERNS = None
    _ERROR_PATTERNS = None

    _RENDER_MOD_KEYWORDS = (
        "iris",
        "oculus",
        "optifine",
        "sodium",
        "indium",
        "rubidium",
        "embeddium",
        "nvidium",
        "canvas",
    )

    _SUGGESTIONS: Dict[str, List[str]] = {
        "Overlay Hook Conflict": [
            "Close overlays/injectors (RTSS/MSI Afterburner, NVIDIA overlay, Discord overlay, OBS hook) and retest.",
        ],
        "Vulkan Surface Conflict": [
            "Disable experimental Vulkan path and retest with stable OpenGL backend first.",
        ],
        "Driver Module Crash": [
            "Perform a clean graphics driver install (stable branch), then verify no third-party hook DLL is injected.",
        ],
        "Video Memory Pressure": [
            "Lower texture resolution and render distance, then retry without heavy shader packs.",
        ],
        "Shader Pipeline": [
            "Disable current shader pack or switch to a known stable preset; update shader-related mods.",
        ],
        "Device Lost": [
            "Check GPU overclock/temperature and close background GPU-heavy apps.",
        ],
        "Render Pipeline": [
            "Temporarily remove newly added render mods and recover with a minimal graphics mod set.",
        ],
        "Context Initialization": [
            "Update graphics driver and verify Java/runtime bitness plus OpenGL support level.",
        ],
        "Driver Compatibility": [
            "Use a driver branch verified by your GPU vendor; avoid beta drivers for crash triage.",
        ],
        "OpenGL Runtime": [
            "Inspect the first OpenGL error near the crash point and downgrade aggressive graphics settings.",
        ],
    }
    
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
    def _get_error_patterns(cls) -> List[Tuple[re.Pattern, str, str, int]]:
        if cls._ERROR_PATTERNS is None:
            patterns = [
                (
                    r"rtsshooks64\.dll|nvspcap64\.dll|discordhook64\.dll|gamebarpresencewriter|obs-graphics-hook",
                    "Overlay Hook Modules Loaded",
                    "Overlay Hook Conflict",
                    4,
                ),
                (
                    r"vk_error_native_window_in_use_khr|vkcreateswapchainkhr\s+failed.*-1000000001|native\s+window\s+in\s+use",
                    "Vulkan Native Window In Use",
                    "Vulkan Surface Conflict",
                    4,
                ),
                (
                    r"exception_access_violation.*(nvoglv|atio6axx|amduw23g|ig\w+|vulkan-1\.dll)",
                    "Driver Module Access Violation",
                    "Driver Module Crash",
                    4,
                ),
                (
                    r"gl_out_of_memory|out\s+of\s+memory\s+allocating\s+texture|video\s+memory\s+exhausted|vram\s+exhausted",
                    "GL_OUT_OF_MEMORY",
                    "Video Memory Pressure",
                    4,
                ),
                (
                    r"vk_error_device_lost|dxgi_error_device_removed|device\s+removed|device\s+lost",
                    "GPU Device Lost",
                    "Device Lost",
                    4,
                ),
                (
                    r"shader\s+compil.*error|shader\s+.*failed\s+to\s+compile|glsl\s+.*error|failed\s+to\s+link\s+program|shader\s+link\s+error",
                    "Shader Compile/Link Error",
                    "Shader Pipeline",
                    3,
                ),
                (
                    r"render\s*thread\s+crashed|tesselat.*failed|chunk\s+render.*failed|framebuffer\s+.*incomplete",
                    "Render Pipeline Failure",
                    "Render Pipeline",
                    3,
                ),
                (
                    r"failed\s+to\s+initialize\s+opengl|no\s+opengl\s+context|wgl:\s*failed\s+to\s+create\s+context|couldn'?t\s+create\s+window",
                    "OpenGL Init Failed",
                    "Context Initialization",
                    3,
                ),
                (
                    r"driver\s+does\s+not\s+.*support\s+opengl|unsupported\s+opengl|opengl\s+version\s+.*not\s+supported",
                    "Driver No OpenGL Support",
                    "Driver Compatibility",
                    3,
                ),
                (
                    r"glfw\s+error\s*[\d\w]+|opengl\s+error\s*[\d\w]+|gl_invalid_operation|gl_invalid_value|gl_invalid_enum|openglexception|glerror\s*\(",
                    "OpenGL Runtime Error",
                    "OpenGL Runtime",
                    2,
                ),
            ]
            cls._ERROR_PATTERNS = [
                (re.compile(pattern, re.IGNORECASE), label, category, severity)
                for pattern, label, category, severity in patterns
            ]
        return cls._ERROR_PATTERNS

    @staticmethod
    def _dedupe_keep_order(values: Iterable[str]) -> List[str]:
        seen = set()
        deduped: List[str] = []
        for value in values:
            if not value:
                continue
            if value in seen:
                continue
            seen.add(value)
            deduped.append(value)
        return deduped

    @staticmethod
    def _first_matching_line(lines: List[str], pattern: re.Pattern[str]) -> str:
        for line in lines:
            if pattern.search(line):
                return line.strip()
        return ""

    def _build_suggestions(self, categories: List[str], render_mods: List[str]) -> List[str]:
        suggestions: List[str] = []
        for category in categories:
            suggestions.extend(self._SUGGESTIONS.get(category, []))

        if render_mods:
            suggestions.append("Detected render mods. Reproduce with a minimal render stack, then add mods back one by one.")

        suggestions.append(
            "If crashes persist, pin Minecraft/Loader/render-mod versions to a known-compatible combination."
        )
        return self._dedupe_keep_order(suggestions)
    
    def detect(self, crash_log: str, context: AnalysisContext) -> List[DetectionResult]:
        analyzer = context.analyzer
        txt = crash_log or ""
        lines = txt.splitlines()

        if not txt.strip():
            return context.results

        # Check noise patterns first
        noise_count = sum(1 for pattern in self._get_noise_patterns() if pattern.search(txt))

        # Collect error matches with categories and evidence
        hits = []
        for pattern, label, category, severity in self._get_error_patterns():
            if not pattern.search(txt):
                continue
            hits.append(
                {
                    "label": label,
                    "category": category,
                    "severity": severity,
                    "evidence": self._first_matching_line(lines, pattern),
                }
            )

        # No real errors, skip
        if not hits:
            return context.results

        # Only noise, skip
        if noise_count > 0 and len(hits) <= 1:
            weak_signals = {"Render Pipeline Failure"}
            if all(hit["label"] in weak_signals for hit in hits):
                return context.results

        labels = self._dedupe_keep_order(str(hit["label"]) for hit in hits)
        categories = self._dedupe_keep_order(str(hit["category"]) for hit in hits)
        evidences = self._dedupe_keep_order(str(hit["evidence"]) for hit in hits if hit.get("evidence"))

        context.add_result(
            "Detected GPU/Driver/GL error:",
            detector=self.get_name(),
            cause_label=CAUSE_GPU
        )
        context.add_result("  - Error types: " + ", ".join(labels), detector=self.get_name())
        context.add_result("  - Signal categories: " + ", ".join(categories), detector=self.get_name())

        for evidence in evidences[:4]:
            context.add_result("  - Evidence: " + evidence, detector=self.get_name())

        # Extract relevant code snippets
        snippets: List[str] = []
        for line in lines:
            if any(pattern.search(line) for pattern, _, _, _ in self._get_error_patterns()):
                snippet = line.strip()
                if snippet and snippet not in snippets:
                    snippets.append(snippet)
                if len(snippets) >= 12:
                    break
        if snippets:
            try:
                setattr(analyzer, "gl_snippets", snippets)
            except Exception:
                pass

        # Collect GPU info
        try:
            if not getattr(analyzer, "gpu_info", None) and hasattr(analyzer, "_collect_system_info"):
                info = analyzer._collect_system_info() or {}
                gpus = info.get("gpus") or {}
                setattr(analyzer, "gpu_info", gpus)
        except Exception:
            pass

        # Check rendering related mods
        render_mods = [
            mod_name
            for mod_name in getattr(analyzer, "mods", {}).keys()
            if any(keyword in mod_name.lower() for keyword in self._RENDER_MOD_KEYWORDS)
        ]
        if render_mods:
            context.add_result("  - Related render/mods: " + ", ".join(sorted(render_mods)), detector=self.get_name())

        suggestions = self._build_suggestions(categories, sorted(render_mods))
        if suggestions:
            context.add_result("Suggestion: " + suggestions[0], detector=self.get_name())
            for suggestion in suggestions[1:4]:
                context.add_result("  - " + suggestion, detector=self.get_name())

        return context.results

    def get_name(self) -> str:
        return "GPUDetector"

    def get_cause_label(self) -> Optional[str]:
        return CAUSE_GPU
