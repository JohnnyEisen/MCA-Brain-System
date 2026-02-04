from __future__ import annotations
import re
from typing import Dict, Pattern

class RegexCache:
    """预编译并缓存正则表达式模式，以避免重复编译开销。"""
    _cache: Dict[str, Pattern] = {}

    @classmethod
    def get(cls, pattern: str, flags: int = 0) -> Pattern:
        key = (pattern, flags)
        if key not in cls._cache:
            cls._cache[key] = re.compile(pattern, flags)
        return cls._cache[key]

    @classmethod
    def search(cls, pattern: str, string: str, flags: int = 0) -> re.Match | None:
        return cls.get(pattern, flags).search(string)

    @classmethod
    def findall(cls, pattern: str, string: str, flags: int = 0) -> list[str]:
        return cls.get(pattern, flags).findall(string)

    @classmethod
    def finditer(cls, pattern: str, string: str, flags: int = 0):
        return cls.get(pattern, flags).finditer(string)
