from __future__ import annotations

from mca_core.detectors.contracts import AnalysisContext
from mca_core.detectors.gl_errors import GlErrorsDetector


class AnalyzerStub:
    def __init__(self, mods: dict[str, set[str]] | None = None) -> None:
        self.analysis_results: list[str] = []
        self.cause_counts: dict[str, int] = {}
        self.lock = None
        self.mods = mods or {}
        self.gpu_info = {}

    def add_cause(self, label: str) -> None:
        self.cause_counts[label] = self.cause_counts.get(label, 0) + 1


def test_gl_errors_detector_detects_overlay_and_vulkan_conflict() -> None:
    log = """
    vkCreateSwapchainKHR failed: VK_RESULT(-1000000001)
    Loaded module: RTSSHooks64.dll
    Render thread crashed
    """
    detector = GlErrorsDetector()
    analyzer = AnalyzerStub(mods={"iris": {"1.6.0"}, "sodium": {"0.5.0"}})
    context = AnalysisContext(analyzer=analyzer, crash_log=log)

    results = detector.detect(log, context)
    assert results

    combined = "\n".join(result.message for result in results)
    assert "Vulkan Surface Conflict" in combined
    assert "Overlay Hook Conflict" in combined
    assert "Related render/mods" in combined
    assert detector.get_cause_label() in context.cause_counts
    assert any("RTSSHooks64.dll" in snippet for snippet in getattr(analyzer, "gl_snippets", []))


def test_gl_errors_detector_skips_weak_render_thread_noise() -> None:
    log = """
    Caught exception in thread \"Render thread\"
    Render thread crashed
    """
    detector = GlErrorsDetector()
    analyzer = AnalyzerStub()
    context = AnalysisContext(analyzer=analyzer, crash_log=log)

    results = detector.detect(log, context)
    assert results == []
