"""正则表达式缓存模块。

预编译并缓存正则表达式模式，避免重复编译开销。
"""
from __future__ import annotations

import re
from typing import Iterator


class RegexCache:
    """预编译并缓存正则表达式模式。

    使用类级别缓存，所有实例共享同一缓存。
    """

    _cache: dict[tuple[str, int], re.Pattern[str]] = {}

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
        if cache_key not in cls._cache:
            cls._cache[cache_key] = re.compile(pattern, flags)
        return cls._cache[cache_key]

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
        cls._cache.clear()
