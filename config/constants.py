import os
import re

# 项目根目录（包含此配置包的文件夹）
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# UI 常量
WINDOW_TITLE = "Minecraft 崩溃分析工具 v1.0 - Brain System"
WINDOW_DEFAULT_SIZE = "1280x850"
WINDOW_MIN_WIDTH = 1000
WINDOW_MIN_HEIGHT = 700

# 项目根目录内的数据目录
BASE_DIR = os.path.join(ROOT_DIR, "analysis_data")
os.makedirs(BASE_DIR, exist_ok=True)

# UI 性能阈值
HIGHLIGHT_SIZE_LIMIT = 300_000
DEFAULT_SCROLL_SENSITIVITY = 3

# 优化 & 限制 (Optimization Limits)
DEFAULT_MAX_BYTES = 8 * 1024 * 1024       # 默认全量读取限制 (8MB)
LAB_HEAD_READ_SIZE = 128 * 1024           # 实验室/训练模式头部读取限制 (128KB)
LAB_SAMPLE_SIZE = 50 * 1024               # 对抗样本生成目标大小 (50KB)
AI_SEMANTIC_LIMIT = 4096                  # 语义向量计算字符截断阈值

# 崩溃原因分类标签
CAUSE_MEM = "内存溢出"
CAUSE_DEP = "缺失依赖"
CAUSE_VER = "版本冲突"
CAUSE_DUP = "重复MOD"
CAUSE_GPU = "GPU/驱动/GL"
CAUSE_GECKO = "GeckoLib缺失/初始化"
CAUSE_OTHER = "其他"

# 持久化文件路径
HISTORY_FILE = os.path.join(BASE_DIR, "crash_analysis_history.csv")
DEPENDENCY_FILE = os.path.join(BASE_DIR, "mod_dependencies.csv")
MOD_DB_FILE = os.path.join(BASE_DIR, "mod_database.json")
LOADER_DB_FILE = os.path.join(BASE_DIR, "loader_database.json")
MOD_CONFLICTS_FILE = os.path.join(BASE_DIR, "mod_conflicts.json")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
GPU_ISSUES_FILE = os.path.join(BASE_DIR, "gpu_issues.json")

# 预编译正则表达式模式
RE_JAR_NAME_VER = re.compile(r"([A-Za-z0-9_.\-]+)-([0-9][A-Za-z0-9\.\-_]+)\.jar")
RE_NAME_MODID_VER = re.compile(r"([^\n\r()]{2,60})\(([\w\-\_]+)\)\s*v?([0-9A-Za-z\.\-\+_]+)")
RE_MODID_AT_VER = re.compile(r"([A-Za-z0-9_.\-]+)@([0-9A-Za-z\.\-\+_]+)")
RE_CTX_DEP = re.compile(r"(?:requires|required|is missing|missing)\s+[:'\"\s]*([A-Za-z0-9_.\-]+)", flags=re.IGNORECASE)
RE_MOD_FALLBACK = re.compile(r"mod\s+['\"]?([A-Za-z0-9_.\-]+)['\"]?", flags=re.IGNORECASE)
RE_DEP_REQUESTED = re.compile(r"Mod ID:\s*'([^']+)'\s*,\s*Requested by:\s*'([^']+)'", flags=re.IGNORECASE)
RE_DEP_REQUIRES = re.compile(r"([A-Za-z0-9_.\-]+)\s+(?:requires|required|depends on|depends)\s+([A-Za-z0-9_.\-]+)", flags=re.IGNORECASE)
RE_REQUESTED_BY = re.compile(r"Requested by:\s*([^,\n\r]+)", flags=re.IGNORECASE)

# 图表配置
GRAPH_NODE_LIMIT = 150
GRAPH_LAYOUT_TIMEOUT = 5.0  # 秒

# UI 逻辑常量
MAX_DISPLAY_ITEMS = 10
DEFAULT_SCROLL_SENSITIVITY = 6
TAIL_REFRESH_INTERVAL_MS = 500
