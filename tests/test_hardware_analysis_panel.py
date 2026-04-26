from mca_core.hardware_analysis import analyze_hardware_log


def test_analyze_hardware_log_high_risk_with_render_mods() -> None:
    log = """
    Failed to initialize OpenGL
    GL_OUT_OF_MEMORY while allocating texture
    Shader compile error at line 12
    """

    result = analyze_hardware_log(
        log,
        current_mods={"iris": {"1.0.0"}, "sodium": {"0.5.0"}},
        system_info={"platform": "Windows-11", "python": "3.13.12"},
        gpu_rules=None,
    )

    assert result["risk_level"] in {"MEDIUM", "HIGH"}
    assert result["risk_score"] >= 7
    assert result["render_mods"] == ["iris", "sodium"]
    assert any("更新显卡驱动" in s or "升级到稳定显卡驱动" in s for s in result["suggestions"])
    assert len(result["snippets"]) >= 1


def test_analyze_hardware_log_vendor_rule_hit() -> None:
    log = "NVIDIA GeForce RTX 4070 detected. OpenGL Error 1282"
    rules = {
        "rules": [
            {
                "vendor": "nvidia",
                "match": ["nvidia", "geforce"],
                "advice": "更新 NVIDIA 驱动到稳定版。",
            }
        ]
    }

    result = analyze_hardware_log(log, gpu_rules=rules)

    assert any("GPU规则命中" in c for c in result["categories"])
    assert any("NVIDIA" in s or "nvidia" in s.lower() for s in result["suggestions"])


def test_analyze_hardware_log_none_when_no_signal() -> None:
    log = "Minecraft started successfully. No crash found."
    result = analyze_hardware_log(log)

    assert result["risk_level"] == "NONE"
    assert result["risk_score"] == 0
    assert result["issues"] == []


def test_analyze_hardware_log_overlay_and_vulkan_conflict() -> None:
    log = """
    vkCreateSwapchainKHR failed: VK_RESULT(-1000000001)
    Loaded module: RTSSHooks64.dll
    """

    result = analyze_hardware_log(log, current_mods={"iris": {"1.6.0"}})

    assert "图形覆盖层/注入冲突" in result["categories"]
    assert "Vulkan窗口占用冲突" in result["categories"]
    assert any("覆盖层" in tip for tip in result["suggestions"])
    assert any("RTSSHooks64.dll" in snippet for snippet in result["snippets"])


def test_analyze_hardware_log_render_core_combo_conflict() -> None:
    log = "Render thread crashed while chunk render pipeline was active"
    result = analyze_hardware_log(
        log,
        current_mods={
            "optifine": {"1.0"},
            "sodium": {"0.5.0"},
            "embeddium": {"0.3.0"},
        },
    )

    assert "渲染核心模组重复叠加" in result["categories"]
    assert "多渲染优化核心并存" in result["categories"]
    assert result["risk_level"] in {"MEDIUM", "HIGH"}
    assert any("保留单一渲染优化核心" in tip for tip in result["suggestions"])
