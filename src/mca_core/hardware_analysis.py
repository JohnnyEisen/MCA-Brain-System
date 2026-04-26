"""Hardware analysis utilities for the PyQt hardware panel."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List


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

_SNIPPET_KEYWORDS = (
    "opengl",
    "glfw",
    "gl_",
    "shader",
    "glsl",
    "gpu",
    "driver",
    "vulkan",
    "dxgi",
    "device_lost",
    "device removed",
    "device lost",
    "render thread",
    "framebuffer",
    "tessellat",
    "swapchain",
    "rtsshooks64.dll",
    "nvspcap64.dll",
    "discordhook64.dll",
)

# (pattern, category, severity, advice)
_PATTERN_RULES = [
    (
        re.compile(
            r"rtsshooks64\.dll|nvspcap64\.dll|discordhook64\.dll|gamebarpresencewriter|obs-graphics-hook",
            re.IGNORECASE,
        ),
        "图形覆盖层/注入冲突",
        4,
        "关闭覆盖层与注入类软件（RTSS/MSI Afterburner、NVIDIA Overlay、Discord Overlay、OBS Hook）后重试。",
    ),
    (
        re.compile(
            r"vk_error_native_window_in_use_khr|vkcreateswapchainkhr\s+failed.*-1000000001|native\s+window\s+in\s+use",
            re.IGNORECASE,
        ),
        "Vulkan窗口占用冲突",
        4,
        "当前窗口已被 OpenGL 路径占用，先回退到稳定 OpenGL 后端或改用隔离窗口的 Vulkan 路径。",
    ),
    (
        re.compile(
            r"exception_access_violation.*(nvoglv|atio6axx|amduw23g|ig\w+|vulkan-1\.dll)",
            re.IGNORECASE,
        ),
        "GPU驱动模块崩溃",
        4,
        "执行显卡驱动干净重装，并排查是否有第三方 DLL 注入图形进程。",
    ),
    (
        re.compile(
            r"failed\s+to\s+initialize\s+opengl|no\s+opengl\s+context|couldn'?t\s+create\s+window|failed\s+to\s+create\s+display|wgl:\s*failed\s+to\s+create\s+context",
            re.IGNORECASE,
        ),
        "OpenGL初始化失败",
        4,
        "更新显卡驱动并确认 Java 位数、渲染后端与当前系统一致。",
    ),
    (
        re.compile(
            r"driver\s+does\s+not\s+.*support\s+opengl|unsupported\s+opengl|opengl\s+version\s+.*not\s+supported",
            re.IGNORECASE,
        ),
        "驱动/版本不兼容",
        3,
        "升级到稳定显卡驱动，必要时回退 Java 或图形模组版本。",
    ),
    (
        re.compile(
            r"gl_out_of_memory|out\s+of\s+memory\s+allocating\s+texture|video\s+memory\s+exhausted|vram\s+exhausted",
            re.IGNORECASE,
        ),
        "显存压力",
        4,
        "降低纹理分辨率与渲染距离，减少光影与高负载渲染模组。",
    ),
    (
        re.compile(
            r"vk_error_device_lost|dxgi_error_device_removed|device\s+removed|device\s+lost",
            re.IGNORECASE,
        ),
        "GPU设备丢失",
        4,
        "检查显卡超频与温度，关闭后台占用 GPU 的程序后重试。",
    ),
    (
        re.compile(
            r"shader\s+compil.*error|shader\s+.*failed\s+to\s+compile|glsl\s+.*error|failed\s+to\s+link\s+program|shader\s+link\s+error",
            re.IGNORECASE,
        ),
        "Shader编译失败",
        3,
        "临时禁用光影包或替换渲染管线相关模组版本。",
    ),
    (
        re.compile(
            r"glfw\s+error|opengl\s+error|gl_invalid_operation|gl_invalid_value|gl_invalid_enum",
            re.IGNORECASE,
        ),
        "OpenGL运行时错误",
        2,
        "重点排查渲染模组冲突，并确认图形驱动安装完整。",
    ),
    (
        re.compile(
            r"render\s*thread\s+crashed|chunk\s+render.*failed|tesselat.*failed|framebuffer\s+.*incomplete|pipeline\s+state\s+invalid",
            re.IGNORECASE,
        ),
        "渲染线程/管线异常",
        2,
        "优先移除近期新增渲染模组，验证是否为组合兼容性问题。",
    ),
    (
        re.compile(r"outofmemoryerror|java\s+heap\s+space", re.IGNORECASE),
        "JVM堆内存压力",
        1,
        "在启动参数中适度提高 -Xmx，并检查是否存在高内存占用模组。",
    ),
    (
        re.compile(r"vulkan", re.IGNORECASE),
        "Vulkan后端相关",
        1,
        "若使用实验性 Vulkan 路径，建议先回退到稳定图形后端验证。",
    ),
]


def _dedupe_keep_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if not value:
            continue
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _find_first_matching_line(lines: List[str], pattern: re.Pattern[str]) -> str:
    for line in lines:
        if pattern.search(line):
            return line.strip()
    return ""


def _extract_pattern_hits(lines: List[str]) -> List[Dict[str, Any]]:
    hits: List[Dict[str, Any]] = []
    seen = set()

    for pattern, category, severity, advice in _PATTERN_RULES:
        evidence = _find_first_matching_line(lines, pattern)
        if not evidence:
            continue

        key = (category, evidence)
        if key in seen:
            continue
        seen.add(key)

        hits.append(
            {
                "category": category,
                "severity": severity,
                "advice": advice,
                "evidence": evidence,
            }
        )

    return hits


def _extract_gpu_rule_hits(lowered: str, gpu_rules: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    if not isinstance(gpu_rules, dict):
        return []

    rules = gpu_rules.get("rules")
    if not isinstance(rules, list):
        return []

    hits: List[Dict[str, Any]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue

        tokens = rule.get("match")
        if not isinstance(tokens, list):
            continue

        normalized_tokens = [str(token).strip().lower() for token in tokens if str(token).strip()]
        if not normalized_tokens:
            continue

        if not any(token in lowered for token in normalized_tokens):
            continue

        vendor = str(rule.get("vendor", "unknown")).strip() or "unknown"
        advice = str(rule.get("advice", "请根据 GPU 厂商规则进一步排查驱动兼容性。"))
        hits.append(
            {
                "category": f"GPU规则命中({vendor})",
                "severity": 2,
                "advice": advice,
                "evidence": f"命中关键词: {', '.join(normalized_tokens)}",
            }
        )

    return hits


def _collect_render_mods(current_mods: Dict[str, Any] | None) -> List[str]:
    if not isinstance(current_mods, dict):
        return []

    matches = []
    for mod_id in current_mods.keys():
        lowered = str(mod_id).lower()
        if any(keyword in lowered for keyword in _RENDER_MOD_KEYWORDS):
            matches.append(str(mod_id))

    return sorted(set(matches))


def _extract_render_combo_hits(render_mods: List[str]) -> List[Dict[str, Any]]:
    if not render_mods:
        return []

    lowered = [mod.lower() for mod in render_mods]

    def _has(keyword: str) -> bool:
        return any(keyword in mod for mod in lowered)

    hits: List[Dict[str, Any]] = []

    if _has("optifine") and (_has("sodium") or _has("embeddium") or _has("rubidium")):
        pair_mods = [
            mod
            for mod in render_mods
            if any(k in mod.lower() for k in ("optifine", "sodium", "embeddium", "rubidium"))
        ]
        hits.append(
            {
                "category": "渲染核心模组重复叠加",
                "severity": 3,
                "advice": "检测到 OptiFine 与 Sodium/Embeddium/Rubidium 同时存在，建议保留单一渲染优化核心。",
                "evidence": f"渲染模组组合: {', '.join(sorted(set(pair_mods)))}",
            }
        )

    performance_core_mods = [
        mod
        for mod in render_mods
        if any(k in mod.lower() for k in ("sodium", "embeddium", "rubidium"))
    ]
    if len(performance_core_mods) >= 2:
        hits.append(
            {
                "category": "多渲染优化核心并存",
                "severity": 3,
                "advice": "Sodium/Embeddium/Rubidium 仅应保留其一，避免渲染注入路径冲突。",
                "evidence": f"渲染模组组合: {', '.join(sorted(set(performance_core_mods)))}",
            }
        )

    if _has("iris") and _has("oculus"):
        hits.append(
            {
                "category": "光影桥接模组重复",
                "severity": 2,
                "advice": "Iris 与 Oculus 通常不应同时启用，请按加载器生态保留单一光影桥接模组。",
                "evidence": "渲染模组组合: Iris + Oculus",
            }
        )

    seen = set()
    deduped_hits: List[Dict[str, Any]] = []
    for hit in hits:
        key = (str(hit.get("category", "")), str(hit.get("evidence", "")))
        if key in seen:
            continue
        seen.add(key)
        deduped_hits.append(hit)
    return deduped_hits


def _collect_snippets(lines: List[str], max_snippets: int) -> List[str]:
    snippets: List[str] = []
    for line in lines:
        lowered = line.lower()
        if any(keyword in lowered for keyword in _SNIPPET_KEYWORDS):
            snippets.append(line.strip())
            if len(snippets) >= max_snippets:
                break
    return snippets


def _risk_level(score: int) -> str:
    if score >= 8:
        return "HIGH"
    if score >= 4:
        return "MEDIUM"
    if score >= 1:
        return "LOW"
    return "NONE"


def analyze_hardware_log(
    log_text: str,
    *,
    current_mods: Dict[str, Any] | None = None,
    system_info: Dict[str, Any] | None = None,
    gpu_rules: Dict[str, Any] | None = None,
    max_snippets: int = 20,
) -> Dict[str, Any]:
    """Analyze hardware/render related signals in crash logs."""
    text = log_text or ""
    lines = [line for line in text.splitlines() if line.strip()]
    lowered = text.lower()
    render_mods = _collect_render_mods(current_mods)

    hits = _extract_pattern_hits(lines)
    hits.extend(_extract_gpu_rule_hits(lowered, gpu_rules))
    hits.extend(_extract_render_combo_hits(render_mods))

    categories = _dedupe_keep_order(hit.get("category", "") for hit in hits)
    suggestions = _dedupe_keep_order(hit.get("advice", "") for hit in hits)

    if render_mods:
        suggestions = _dedupe_keep_order(
            suggestions
            + [
                "检测到渲染相关模组，建议先用最小渲染模组组合复现，再逐步恢复。",
            ]
        )

    snippets = _collect_snippets(lines, max_snippets)
    if not snippets:
        snippets = [str(hit.get("evidence", "")) for hit in hits if hit.get("evidence")][:max_snippets]

    score = sum(int(hit.get("severity", 1)) for hit in hits)
    if render_mods and categories:
        score += 1

    return {
        "risk_level": _risk_level(score),
        "risk_score": score,
        "categories": categories,
        "issues": hits,
        "suggestions": suggestions,
        "render_mods": render_mods,
        "snippets": snippets,
        "system_info": system_info or {},
    }
