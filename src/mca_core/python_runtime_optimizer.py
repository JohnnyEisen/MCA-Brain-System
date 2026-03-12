import sys
import gc
import platform
import logging
import os

_VALID_MODES = {"slight", "standard", "aggressive"}
_MODE_ALIASES = {
    # Chinese aliases
    "略微": "slight", "轻度": "slight", "轻微": "slight",
    "标准": "standard", "默认": "standard",
    "激进": "aggressive", "高强度": "aggressive",
    # English aliases (self-mapping)
    "slight": "slight",
    "standard": "standard",
    "aggressive": "aggressive"
}

# 优化配置文件 (集中管理参数，避免 Magic Numbers)
OPTIMIZATION_PROFILES = {
    "python3.8+": {
        "slight": {"gc_threshold": (800, 11, 11), "switch_interval": 0.006},
        "standard": {"gc_threshold": (900, 12, 12), "switch_interval": 0.005},
        "aggressive": {"gc_threshold": (1100, 14, 14), "switch_interval": 0.003},
    },
    "python3.13_gil": {
        # 3.13 GIL 模式稳定/极端参数
        "slight": {"gc_threshold": (800, 11, 11)},
        "standard": {"gc_threshold": (900, 12, 12)},
        "aggressive": {"gc_threshold": (1100, 14, 14)},
    },
    "python3.11+": {
        # 3.11+ 分配更快，调整分代策略
        "slight": {"gc_threshold": (900, 12, 18)},
        "standard": {"gc_threshold": (1000, 15, 20)},
        "aggressive": {"gc_threshold": (1300, 18, 24)},
    },
    "python3.13_nogil": {
        # Free-threaded 模式需要大幅降低 GC 频率
        "slight": {"gc_threshold": (1500, 16, 16)},
        "standard": {"gc_threshold": (2000, 20, 20)},
        "aggressive": {"gc_threshold": (2600, 24, 24)},
    }
}

# 优化模式描述文本 (用于 UI 显示)
MODE_DESCRIPTIONS = [
    ("略微", "保守策略 - 适合低内存环境，减少内存占用但可能增加 CPU 消耗。"),
    ("标准", "推荐配置 - 平衡内存回收频率与分析吞吐量，适合大多数场景。"),
    ("激进", "高性能 - 减少 GC 频率，大幅提升大文件分析速度，但内存占用较高。")
]

def apply_version_specific_optimizations(mode: str = "standard"):
    """
    根据当前运行的 Python 版本应用特定的运行时优化配置。
    """
    version = sys.version_info
    major, minor = version.major, version.minor
    
    logger = logging.getLogger("mca_core.optimizer")
    
    # --- 1. 参数验证与规范化 ---
    # 允许通过环境变量覆盖 mode，方便调试/基准测试
    env_mode = os.environ.get("MCA_OPT_MODE", "").strip()
    raw_mode = env_mode or (str(mode).strip() if mode else "standard")
    # 尝试映射别名，如果不在别名表中，尝试忽略大小写匹配，否则回退到 standard
    normalized_mode = _MODE_ALIASES.get(raw_mode, _MODE_ALIASES.get(raw_mode.lower(), "standard"))
    
    if normalized_mode not in _VALID_MODES:
        logger.warning(f"检测到无效的优化模式 '{raw_mode}'，安全回退到 'standard'")
        normalized_mode = "standard"

    logger.info(f"环境检测: Python {platform.python_version()} ({platform.platform()})")
    logger.info(f"应用运行时优化: '{normalized_mode}' (原始输入: {raw_mode})")

    # --- 2. 应用全局安全设置 ---
    _apply_global_security_settings()

    if major < 3 or (major == 3 and minor < 8):
        logger.warning("Python 版本过低 (<3.8)，跳过运行时优化。")
        return

    # 确保 GC 启用
    if not gc.isenabled():
        gc.enable()

    # --- 3. 基于配置文件的参数应用 ---
    # 确定配置组
    profile_key = "python3.8+"
    if minor >= 13:
        # 3.13 特殊检测
        if hasattr(sys, "_is_gil_enabled") and not sys._is_gil_enabled():
            profile_key = "python3.13_nogil"
            logger.info("检测到 Free-threaded (No-GIL) 模式，应用并发优化配置。")
        else:
            profile_key = "python3.13_gil"
    elif minor >= 11:
         profile_key = "python3.11+"

    # 获取参数集
    profile = OPTIMIZATION_PROFILES.get(profile_key, OPTIMIZATION_PROFILES["python3.8+"])
    params = profile.get(normalized_mode, profile["standard"])

    # --- 3.5 允许通过环境变量覆盖参数 (便于调试) ---
    # MCA_GC_THRESHOLD 格式: "g0,g1,g2"，例如 "1200,16,16"
    # MCA_SWITCH_INTERVAL 格式: "0.004"
    env_gc = os.environ.get("MCA_GC_THRESHOLD", "").strip()
    env_switch = os.environ.get("MCA_SWITCH_INTERVAL", "").strip()
    if env_gc:
        try:
            parts = [int(x.strip()) for x in env_gc.split(",")]
            if len(parts) == 3:
                params = dict(params)
                params["gc_threshold"] = tuple(parts)
                logger.info(f"环境变量覆盖 GC 阈值: {params['gc_threshold']}")
            else:
                logger.warning(f"MCA_GC_THRESHOLD 格式无效: {env_gc}")
        except Exception:
            logger.warning(f"MCA_GC_THRESHOLD 解析失败: {env_gc}")

    if env_switch:
        try:
            switch_val = float(env_switch)
            params = dict(params)
            params["switch_interval"] = switch_val
            logger.info(f"环境变量覆盖 switch_interval: {switch_val}")
        except Exception:
            logger.warning(f"MCA_SWITCH_INTERVAL 解析失败: {env_switch}")

    # 应用 GC 阈值
    if "gc_threshold" in params:
        g0, g1, g2 = params["gc_threshold"]
        logger.info(f"设置 GC 阈值: ({g0}, {g1}, {g2})")
        gc.set_threshold(g0, g1, g2)

    # 应用 switch interval (仅 3.8/3.9/3.10 可能需要，3.11+ 通常无需干预)
    if minor <= 10 and "switch_interval" in params:
        interval = params["switch_interval"]
        logger.info(f"设置 sys.setswitchinterval: {interval}s")
        sys.setswitchinterval(interval)

    # --- 4. 版本特定的额外非参数化逻辑 ---
    if minor == 10 and normalized_mode == "aggressive":
        # 3.10 激进模式下的强制回收
        logger.info("Python 3.10 Aggressive: 执行启动时深度回收")
        gc.collect(2)
        
    if minor >= 12 and normalized_mode != "slight":
        try:
            # 3.12+ 减少异步生成器钩子开销
            sys.set_asyncgen_hooks(firstiter=None, finalizer=None)
        except AttributeError:
            pass

    if minor >= 15:
         logger.warning("正在使用 Python 预览版本 (3.15+)，优化策略可能未完全适配。")

def _apply_global_security_settings():
    """应用全局解释器安全限制放宽 (针对大数处理)"""
    # 默认限制为 4300，这里放宽到 10000 以支持深度堆栈分析
    try:
        if hasattr(sys, "set_int_max_str_digits"):
             current_limit = sys.get_int_max_str_digits()
             # 只有当当前限制过于严格时才放宽，避免覆盖用户的更高设置
             if current_limit < 10000:
                 sys.set_int_max_str_digits(10000)
    except (AttributeError, ValueError):
        pass


