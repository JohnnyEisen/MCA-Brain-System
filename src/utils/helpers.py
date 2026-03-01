"""Mod ID 清洗与规范化工具模块。

提供 Mod ID 的清洗、相似度计算和规范化功能。
"""

from __future__ import annotations

import re
from typing import AbstractSet

__all__ = [
    "mca_clean_modid",
    "mca_levenshtein",
    "mca_normalize_modid",
]

# 用于提高性能的预编译正则模式
RE_CLEAN_INVALID: re.Pattern[str] = re.compile(r"[^A-Za-z0-9_.\-]")
RE_CLEAN_LEADING: re.Pattern[str] = re.compile(r"^[0-9\-_]+")
RE_HAS_ALPHA: re.Pattern[str] = re.compile(r"[A-Za-z]")

# 常用忽略词集合（使用字面量提高速度）
IGNORE_WORDS: set[str] = {
    "mods.toml", "mods.toml file", "mods.tomlfile",
    "sound", "state", "unknown", "missing",
    "mod", "modfile", "mod file", "jar", "file", "or", "id"
}


def mca_clean_modid(raw: str | None) -> str | None:
    """清洗 Mod ID 字符串。

    移除无效字符、前导数字和下划线，过滤无效的标识符。

    Args:
        raw: 原始 Mod ID 字符串。

    Returns:
        清洗后的 Mod ID，若无效则返回 None。
    """
    if not raw:
        return None
    # 使用预编译正则
    mid = RE_CLEAN_INVALID.sub("", raw).strip()
    if not mid:
        return None
    mid = RE_CLEAN_LEADING.sub("", mid)

    # 使用预编译正则搜索
    if not RE_HAS_ALPHA.search(mid):
        return None

    low = mid.lower()
    if low in IGNORE_WORDS or len(low) < 2:
        return None
    return mid


def mca_levenshtein(a: str, b: str) -> int:
    """计算两个字符串之间的 Levenshtein 编辑距离。

    Args:
        a: 第一个字符串。
        b: 第二个字符串。

    Returns:
        编辑距离（非负整数）。
    """
    if a == b:
        return 0
    la, lb = len(a), len(b)
    if la == 0:
        return lb
    if lb == 0:
        return la
    prev = list(range(lb + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i] + [0] * lb
        for j, cb in enumerate(b, start=1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[lb]


def mca_normalize_modid(
    name: str | None,
    mods_keys: AbstractSet[str],
    mod_names: dict[str, str] | None,
) -> str | None:
    """规范化 Mod ID，尝试匹配已知 Mod 列表。

    依次尝试精确匹配、忽略大小写匹配、显示名匹配、模糊匹配（编辑距离 <= 2）。

    Args:
        name: 待规范化的 Mod ID 或名称。
        mods_keys: 已知 Mod ID 集合。
        mod_names: Mod ID 到显示名的映射字典。

    Returns:
        规范化后的 Mod ID，若无法匹配则返回 None。
    """
    if not name:
        return None
    cand = name.strip()
    if cand in mods_keys:
        return cand
    low = cand.lower()
    for modid in mods_keys:
        if modid.lower() == low:
            return modid
    for modid, disp in (mod_names or {}).items():
        if disp and disp.lower() == low:
            return modid
    best: str | None = None
    best_score = 999
    for modid in mods_keys:
        dist = mca_levenshtein(low, modid.lower())
        if dist < best_score and dist <= 2:
            best_score = dist
            best = modid
    return best
