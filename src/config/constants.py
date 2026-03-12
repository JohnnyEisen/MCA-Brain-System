"""Application constants module.

Defines project paths, UI parameters, regex patterns, etc.
"""
from __future__ import annotations

import os
import re

# Windows reserved device names
_WINDOWS_RESERVED_NAMES = {'nul', 'aux', 'con', 'prn', 'com1', 'com2', 'com3', 'com4', 
                           'lpt1', 'lpt2', 'lpt3'}

def safe_path(path: str) -> str:
    """Safely handle file paths, prevent Windows reserved device names"""
    if not path:
        return path
    
    basename = os.path.basename(path)
    if basename.lower() in _WINDOWS_RESERVED_NAMES:
        raise ValueError(f"Unsafe filename detected: {basename}")
    
    return path


# ==================== Project Paths ====================

# src directory
SRC_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Project root (parent of src)
ROOT_DIR: str = os.path.dirname(SRC_DIR)

# Data directory
DATA_DIR: str = os.path.join(ROOT_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# Legacy alias
BASE_DIR: str = DATA_DIR

# Logs directory
LOGS_DIR: str = os.path.join(ROOT_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

# ==================== UI Constants ====================

WINDOW_TITLE: str = "Minecraft Crash Analyzer v1.1.0"
WINDOW_DEFAULT_SIZE: str = "1280x850"
WINDOW_MIN_WIDTH: int = 1000
WINDOW_MIN_HEIGHT: int = 700

# UI performance thresholds
HIGHLIGHT_SIZE_LIMIT: int = 300_000
DEFAULT_SCROLL_SENSITIVITY: int = 6
MAX_LOG_LINE_LENGTH: int = 2000

# ==================== Security Limits (V-008 Fix) ====================
MAX_FILE_SIZE_HARD_LIMIT: int = 100 * 1024 * 1024  # 100MB hard limit - reject larger files

# ==================== Optimization Limits ====================
DEFAULT_MAX_BYTES: int = 8 * 1024 * 1024  # 8MB
LAB_HEAD_READ_SIZE: int = 128 * 1024  # 128KB
LAB_SAMPLE_SIZE: int = 50 * 1024  # 50KB
AI_SEMANTIC_LIMIT: int = 4096

# ==================== Crash Cause Labels ====================

CAUSE_MEM: str = "内存溢出"
CAUSE_DEP: str = "缺失依赖"
CAUSE_VER: str = "版本冲突"
CAUSE_DUP: str = "重复Mod"
CAUSE_GPU: str = "显卡/渲染"
CAUSE_GECKO: str = "GeckoLib 缺失"
CAUSE_OTHER: str = "其他"
# ==================== File Paths ====================

# Rules
RULES_DIR: str = os.path.join(DATA_DIR, "rules")
HISTORY_DIR: str = os.path.join(DATA_DIR, "history")

HISTORY_FILE: str = os.path.join(HISTORY_DIR, "crash_analysis_history.csv")
DEPENDENCY_FILE: str = os.path.join(DATA_DIR, "mod_dependencies.csv")
MOD_DB_FILE: str = os.path.join(RULES_DIR, "mod_database.json")
LOADER_DB_FILE: str = os.path.join(RULES_DIR, "loader_database.json")
MOD_CONFLICTS_FILE: str = os.path.join(RULES_DIR, "mod_conflicts.json")
CONFIG_FILE: str = os.path.join(DATA_DIR, "config.json")
GPU_ISSUES_FILE: str = os.path.join(RULES_DIR, "gpu_issues.json")
DIAGNOSTIC_RULES_FILE: str = os.path.join(RULES_DIR, "diagnostic_rules.json")

# Database
DATABASE_FILE: str = os.path.join(DATA_DIR, "mca_data.db")

# Learning/Auto-test outputs
AUTO_TESTS_DIR: str = os.path.join(DATA_DIR, "auto_tests")
LAB_RUNS_DIR: str = os.path.join(DATA_DIR, "lab_runs")
LEARNED_PATTERNS_FILE: str = os.path.join(DATA_DIR, "learned_patterns.json")

# Ensure directories exist
os.makedirs(RULES_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)
os.makedirs(AUTO_TESTS_DIR, exist_ok=True)
os.makedirs(LAB_RUNS_DIR, exist_ok=True)

# ==================== Precompiled Regex ====================

RE_JAR_NAME_VER: re.Pattern[str] = re.compile(
    r"([A-Za-z0-9_.\-]+)-([0-9][A-Za-z0-9\.\-_]+)\.jar"
)
RE_NAME_MODID_VER: re.Pattern[str] = re.compile(
    r"([^\n\r()]{2,60})\(([\w\-\_]+)\)\s*v?([0-9A-Za-z\.\-\+_]+)"
)
RE_MODID_AT_VER: re.Pattern[str] = re.compile(
    r"([A-Za-z0-9_.\-]+)@([0-9A-Za-z\.\-\+_]+)"
)
RE_CTX_DEP: re.Pattern[str] = re.compile(
    r"(?:requires|required|is missing|missing)\s+[:'\"]*\s*([A-Za-z0-9_.\-]+)",
    flags=re.IGNORECASE,
)
RE_MOD_FALLBACK: re.Pattern[str] = re.compile(
    r"mod\s+['\"]?([A-Za-z0-9_.\-]+)['\"]?", flags=re.IGNORECASE
)
RE_DEP_REQUESTED: re.Pattern[str] = re.compile(
    r"Mod ID:\s*'([^']+)'\s*,\s*Requested by:\s*'([^']+)'",
    flags=re.IGNORECASE,
)
RE_DEP_REQUIRES: re.Pattern[str] = re.compile(
    r"([A-Za-z0-9_.\-]+)\s+(?:requires|required|depends on|depends)\s+([A-Za-z0-9_.\-]+)",
    flags=re.IGNORECASE,
)
RE_REQUESTED_BY: re.Pattern[str] = re.compile(
    r"Requested by:\s*([^,\n\r]+)", flags=re.IGNORECASE
)

# ==================== Chart Config ====================

GRAPH_NODE_LIMIT: int = 150
GRAPH_LAYOUT_TIMEOUT: float = 5.0

# ==================== UI Logic ====================

MAX_DISPLAY_ITEMS: int = 10
TAIL_REFRESH_INTERVAL_MS: int = 500
