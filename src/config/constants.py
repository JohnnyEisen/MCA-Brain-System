"""
应用常量模块

定义项目路径、UI 参数、正则表达式模式等常量。

模块说明:
    本模块集中管理应用程序的所有常量定义，包括:
    - 项目路径
    - UI 参数
    - 安全限制
    - 优化限制
    - 崩溃原因标签
    - 文件路径
    - 预编译正则表达式
    - 图表配置
"""

from __future__ import annotations

import os
import re
from typing import Final, Set


# ============================================================
# 安全工具函数 - Security Utilities
# ============================================================

_WINDOWS_RESERVED_NAMES: Final[Set[str]] = {
    'nul', 'aux', 'con', 'prn',
    'com1', 'com2', 'com3', 'com4',
    'lpt1', 'lpt2', 'lpt3'
}


def safe_path(path: str) -> str:
    """
    安全处理文件路径，防止 Windows 保留设备名称。
    
    Args:
        path: 原始文件路径
        
    Returns:
        验证后的文件路径
        
    Raises:
        ValueError: 如果文件名是 Windows 保留设备名称
    """
    if not path:
        return path
    
    basename = os.path.basename(path)
    if basename.lower() in _WINDOWS_RESERVED_NAMES:
        raise ValueError(f"Unsafe filename detected: {basename}")
    
    return path


# ============================================================
# 项目路径 - Project Paths
# ============================================================

SRC_DIR: Final[str] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR: Final[str] = os.path.dirname(SRC_DIR)
DATA_DIR: Final[str] = os.path.join(ROOT_DIR, "data")
BASE_DIR: Final[str] = DATA_DIR
LOGS_DIR: Final[str] = os.path.join(ROOT_DIR, "logs")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)


# ============================================================
# UI 常量 - UI Constants
# ============================================================

WINDOW_TITLE: Final[str] = "Minecraft Crash Analyzer v1.5.0"
WINDOW_DEFAULT_SIZE: Final[str] = "1280x850"
WINDOW_MIN_WIDTH: Final[int] = 1000
WINDOW_MIN_HEIGHT: Final[int] = 700

HIGHLIGHT_SIZE_LIMIT: Final[int] = 300_000
DEFAULT_SCROLL_SENSITIVITY: Final[int] = 6
MAX_LOG_LINE_LENGTH: Final[int] = 2000


# ============================================================
# 安全限制 - Security Limits
# ============================================================

MAX_FILE_SIZE_HARD_LIMIT: Final[int] = 100 * 1024 * 1024


# ============================================================
# 优化限制 - Optimization Limits
# ============================================================

DEFAULT_MAX_BYTES: Final[int] = 8 * 1024 * 1024
LAB_HEAD_READ_SIZE: Final[int] = 128 * 1024
LAB_SAMPLE_SIZE: Final[int] = 50 * 1024
AI_SEMANTIC_LIMIT: Final[int] = 4096


# ============================================================
# 崩溃原因标签 - Crash Cause Labels
# ============================================================

CAUSE_MEM: Final[str] = "内存溢出"
CAUSE_DEP: Final[str] = "缺失依赖"
CAUSE_VER: Final[str] = "版本冲突"
CAUSE_DUP: Final[str] = "重复Mod"
CAUSE_GPU: Final[str] = "显卡/渲染"
CAUSE_GECKO: Final[str] = "GeckoLib 缺失"
CAUSE_OTHER: Final[str] = "其他"


# ============================================================
# 文件路径 - File Paths
# ============================================================

RULES_DIR: Final[str] = os.path.join(DATA_DIR, "rules")
HISTORY_DIR: Final[str] = os.path.join(DATA_DIR, "history")

HISTORY_FILE: Final[str] = os.path.join(HISTORY_DIR, "crash_analysis_history.csv")
DEPENDENCY_FILE: Final[str] = os.path.join(DATA_DIR, "mod_dependencies.csv")
MOD_DB_FILE: Final[str] = os.path.join(RULES_DIR, "mod_database.json")
LOADER_DB_FILE: Final[str] = os.path.join(RULES_DIR, "loader_database.json")
MOD_CONFLICTS_FILE: Final[str] = os.path.join(RULES_DIR, "mod_conflicts.json")
CONFIG_FILE: Final[str] = os.path.join(DATA_DIR, "config.json")
GPU_ISSUES_FILE: Final[str] = os.path.join(RULES_DIR, "gpu_issues.json")
DIAGNOSTIC_RULES_FILE: Final[str] = os.path.join(RULES_DIR, "diagnostic_rules.json")
DATABASE_FILE: Final[str] = os.path.join(DATA_DIR, "mca_data.db")
AUTO_TESTS_DIR: Final[str] = os.path.join(DATA_DIR, "auto_tests")
LAB_RUNS_DIR: Final[str] = os.path.join(DATA_DIR, "lab_runs")
LEARNED_PATTERNS_FILE: Final[str] = os.path.join(DATA_DIR, "learned_patterns.json")

os.makedirs(RULES_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(AUTO_TESTS_DIR, exist_ok=True)
os.makedirs(LAB_RUNS_DIR, exist_ok=True)


# ============================================================
# 预编译正则表达式 - Precompiled Regex Patterns
# ============================================================

RE_JAR_NAME_VER: Final[re.Pattern[str]] = re.compile(
    r"([A-Za-z0-9_.\-]+)-([0-9][A-Za-z0-9\.\-_]+)\.jar"
)
RE_NAME_MODID_VER: Final[re.Pattern[str]] = re.compile(
    r"([^\n\r()]{2,60})\(([\w\-\_]+)\)\s*v?([0-9A-Za-z\.\-\+_]+)"
)
RE_MODID_AT_VER: Final[re.Pattern[str]] = re.compile(
    r"([A-Za-z0-9_.\-]+)@([0-9A-Za-z\.\-\+_]+)"
)
RE_CTX_DEP: Final[re.Pattern[str]] = re.compile(
    r"(?:requires|required|is missing|missing)\s+[:'\"]*\s*([A-Za-z0-9_.\-]+)",
    flags=re.IGNORECASE,
)
RE_MOD_FALLBACK: Final[re.Pattern[str]] = re.compile(
    r"mod\s+['\"]?([A-Za-z0-9_.\-]+)['\"]?",
    flags=re.IGNORECASE
)
RE_DEP_REQUESTED: Final[re.Pattern[str]] = re.compile(
    r"Mod ID:\s*'([^']+)'\s*,\s*Requested by:\s*'([^']+)'",
    flags=re.IGNORECASE,
)
RE_DEP_REQUIRES: Final[re.Pattern[str]] = re.compile(
    r"([A-Za-z0-9_.\-]+)\s+(?:requires|required|depends on|depends)\s+([A-Za-z0-9_.\-]+)",
    flags=re.IGNORECASE,
)
RE_REQUESTED_BY: Final[re.Pattern[str]] = re.compile(
    r"Requested by:\s*([^,\n\r]+)",
    flags=re.IGNORECASE
)


# ============================================================
# 图表配置 - Chart Configuration
# ============================================================

GRAPH_NODE_LIMIT: Final[int] = 150
GRAPH_LAYOUT_TIMEOUT: Final[float] = 5.0


# ============================================================
# UI 逻辑 - UI Logic
# ============================================================

MAX_DISPLAY_ITEMS: Final[int] = 10
TAIL_REFRESH_INTERVAL_MS: Final[int] = 500
