"""正则表达式缓存模块。

预编译并缓存正则表达式模式，避免重复编译开销。
支持 LRU 淘汰策略防止内存无限增长。
"""
from __future__ import annotations

import re
from collections import OrderedDict
from threading import RLock
from typing import Iterator


class RegexCache:
    """预编译并缓存正则表达式模式。

    使用类级别缓存，所有实例共享同一缓存。
    支持 LRU 淘汰策略，限制缓存大小防止内存泄漏。
    """

    _cache: OrderedDict[tuple[str, int], re.Pattern[str]] = OrderedDict()
    _lock: RLock = RLock()
    _max_size: int = 500
    _hits: int = 0
    _misses: int = 0

    @classmethod
    def _ensure_ordered_cache(cls) -> None:
        """确保缓存容器为 OrderedDict。"""
        if not isinstance(cls._cache, OrderedDict):
            cls._cache = OrderedDict(cls._cache)

    @classmethod
    def set_max_size(cls, max_size: int) -> None:
        """设置缓存最大条目数。

        Args:
            max_size: 最大缓存条目数，必须大于 0。
        """
        if max_size <= 0:
            raise ValueError("max_size must be > 0")
        with cls._lock:
            cls._ensure_ordered_cache()
            cls._max_size = max_size
            while len(cls._cache) > cls._max_size:
                cls._cache.popitem(last=False)

    @classmethod
    def get(cls, pattern: str, flags: int = 0) -> re.Pattern[str]:
        """获取或创建编译后的正则表达式。

        Args:
            pattern: 正则表达式模式字符串。
            flags: 正则表达式标志。

        Returns:
            编译后的正则表达式对象。
        """
        cache_key = (pattern, flags)
        with cls._lock:
            cls._ensure_ordered_cache()
            if cache_key in cls._cache:
                cls._hits += 1
                cls._cache.move_to_end(cache_key)
                return cls._cache[cache_key]
            cls._misses += 1
            if len(cls._cache) >= cls._max_size:
                cls._cache.popitem(last=False)
            compiled = re.compile(pattern, flags)
            cls._cache[cache_key] = compiled
            return compiled

    @classmethod
    def search(
        cls, pattern: str, string: str, flags: int = 0
    ) -> re.Match[str] | None:
        """在字符串中搜索模式匹配。

        Args:
            pattern: 正则表达式模式字符串。
            string: 要搜索的字符串。
            flags: 正则表达式标志。

        Returns:
            匹配对象或 None。
        """
        return cls.get(pattern, flags).search(string)

    @classmethod
    def findall(cls, pattern: str, string: str, flags: int = 0) -> list[str]:
        """查找所有匹配项。

        Args:
            pattern: 正则表达式模式字符串。
            string: 要搜索的字符串。
            flags: 正则表达式标志。

        Returns:
            所有匹配的字符串列表。
        """
        return cls.get(pattern, flags).findall(string)

    @classmethod
    def finditer(
        cls, pattern: str, string: str, flags: int = 0
    ) -> Iterator[re.Match[str]]:
        """返回所有匹配的迭代器。

        Args:
            pattern: 正则表达式模式字符串。
            string: 要搜索的字符串。
            flags: 正则表达式标志。

        Returns:
            匹配对象的迭代器。
        """
        return cls.get(pattern, flags).finditer(string)

    @classmethod
    def clear(cls) -> None:
        """清空缓存，释放内存。"""
        with cls._lock:
            cls._ensure_ordered_cache()
            cls._cache.clear()
            cls._hits = 0
            cls._misses = 0

    @classmethod
    def get_stats(cls) -> dict[str, int | float]:
        """获取缓存统计信息。

        Returns:
            包含缓存大小和最大限制的字典。
        """
        with cls._lock:
            total = cls._hits + cls._misses
            return {
                "size": len(cls._cache),
                "max_size": cls._max_size,
                "hits": cls._hits,
                "misses": cls._misses,
                "hit_rate": cls._hits / total if total else 0.0,
            }
