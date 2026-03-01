"""LRU + TTL 缓存模块。

提供带时间到期的最近最少使用缓存实现。
"""
from __future__ import annotations

import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any


def _estimate_size(obj: Any) -> int:
    """估算对象的内存大小（字节）。

    这是一个粗略估算，用于内存限制。
    对于基本类型使用精确值，复杂类型使用递归估算。

    Args:
        obj: 要估算的对象。

    Returns:
        估算的字节数。
    """
    # 基本类型直接使用 sys.getsizeof
    if isinstance(obj, (str, bytes, int, float, bool, type(None))):
        return sys.getsizeof(obj)

    # 列表和元组
    if isinstance(obj, (list, tuple)):
        return sys.getsizeof(obj) + sum(_estimate_size(item) for item in obj[:100])  # 限制递归深度

    # 字典
    if isinstance(obj, dict):
        size = sys.getsizeof(obj)
        for i, (k, v) in enumerate(obj.items()):
            if i >= 100:  # 限制递归深度
                break
            size += _estimate_size(k) + _estimate_size(v)
        return size

    # 集合
    if isinstance(obj, (set, frozenset)):
        return sys.getsizeof(obj) + sum(_estimate_size(item) for item in list(obj)[:100])

    # 其他对象
    try:
        return sys.getsizeof(obj)
    except Exception:
        return 1024  # 默认估算 1KB


@dataclass(slots=True)
class CacheItem:
    """缓存项：存储值和过期时间。

    Attributes:
        value: 缓存的值。
        expires_at: 过期时间戳（秒）。
        size_bytes: 估算的字节大小。
    """

    value: Any
    expires_at: float
    size_bytes: int = 0


class LruTtlCache:
    """LRU + TTL 缓存。

    特性：
    - max_entries: 最大条目数
    - max_bytes: 最大字节数（可选）
    - ttl_seconds: 每个条目的存活时间
    - get() 会刷新 LRU 顺序
    - 过期条目会在访问/写入时惰性清理

    Attributes:
        hits: 缓存命中次数。
        misses: 缓存未命中次数。
        evictions: 驱逐次数。
        expired: 过期清理次数。
        current_bytes: 当前字节数。
    """

    def __init__(
        self,
        *,
        max_entries: int,
        ttl_seconds: float,
        max_bytes: int | None = None,
    ) -> None:
        """初始化缓存。

        Args:
            max_entries: 最大条目数，必须大于 0。
            ttl_seconds: 条目存活时间（秒），必须大于 0。
            max_bytes: 最大字节数（可选），None 表示不限制。

        Raises:
            ValueError: 参数不合法。
        """
        if max_entries <= 0:
            raise ValueError("max_entries must be > 0")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")

        self._max_entries: int = int(max_entries)
        self._ttl_seconds: float = float(ttl_seconds)
        self._max_bytes: int | None = max_bytes
        self._items: OrderedDict[str, CacheItem] = OrderedDict()
        self._current_bytes: int = 0

        self.hits: int = 0
        self.misses: int = 0
        self.evictions: int = 0
        self.expired: int = 0

    @property
    def max_entries(self) -> int:
        """获取最大条目数。"""
        return self._max_entries

    @property
    def ttl_seconds(self) -> float:
        """获取条目存活时间。"""
        return self._ttl_seconds

    @property
    def max_bytes(self) -> int | None:
        """获取最大字节数。"""
        return self._max_bytes

    @property
    def current_bytes(self) -> int:
        """获取当前字节数。"""
        return self._current_bytes

    def __len__(self) -> int:
        """返回当前条目数。"""
        return len(self._items)

    def set_limits(
        self,
        *,
        max_entries: int | None = None,
        ttl_seconds: float | None = None,
        max_bytes: int | None = None,
    ) -> None:
        """动态调整缓存限制。

        Args:
            max_entries: 新的最大条目数（可选）。
            ttl_seconds: 新的存活时间（可选）。
            max_bytes: 新的最大字节数（可选）。

        Raises:
            ValueError: 参数不合法。
        """
        if max_entries is not None:
            if max_entries <= 0:
                raise ValueError("max_entries must be > 0")
            self._max_entries = int(max_entries)
        if ttl_seconds is not None:
            if ttl_seconds <= 0:
                raise ValueError("ttl_seconds must be > 0")
            self._ttl_seconds = float(ttl_seconds)
        if max_bytes is not None:
            self._max_bytes = max_bytes if max_bytes > 0 else None

        self._evict_if_needed()

    def _now(self) -> float:
        """获取当前时间戳。"""
        return time.time()

    def _is_expired(self, item: CacheItem, now: float) -> bool:
        """检查条目是否过期。"""
        return item.expires_at <= now

    def _purge_expired_front(self) -> None:
        """从最旧一侧清理过期条目。"""
        now = self._now()
        keys_to_delete: list[str] = []
        for key, item in self._items.items():
            if self._is_expired(item, now):
                keys_to_delete.append(key)
                self._current_bytes -= item.size_bytes
            else:
                break
        for key in keys_to_delete:
            self._items.pop(key, None)
            self.expired += 1

    def _evict_if_needed(self) -> None:
        """在需要时驱逐条目。"""
        self._purge_expired_front()

        # 按条目数驱逐
        while len(self._items) > self._max_entries:
            key, item = self._items.popitem(last=False)
            self._current_bytes -= item.size_bytes
            self.evictions += 1

        # 按字节数驱逐
        if self._max_bytes is not None:
            while self._current_bytes > self._max_bytes and self._items:
                key, item = self._items.popitem(last=False)
                self._current_bytes -= item.size_bytes
                self.evictions += 1

    def get(self, key: str) -> Any:
        """获取缓存值。

        Args:
            key: 缓存键。

        Returns:
            缓存值，若不存在或已过期则返回 None。
        """
        now = self._now()
        item = self._items.get(key)
        if item is None:
            self.misses += 1
            return None
        if self._is_expired(item, now):
            self._items.pop(key, None)
            self._current_bytes -= item.size_bytes
            self.expired += 1
            self.misses += 1
            return None

        self._items.move_to_end(key, last=True)
        self.hits += 1
        return item.value

    def set(self, key: str, value: Any) -> None:
        """设置缓存值。

        Args:
            key: 缓存键。
            value: 缓存值。
        """
        # 如果键已存在，先减去旧值的大小
        if key in self._items:
            old_item = self._items[key]
            self._current_bytes -= old_item.size_bytes

        # 估算新值大小
        size_bytes = _estimate_size(value)
        expires_at = self._now() + self._ttl_seconds

        self._items[key] = CacheItem(
            value=value, expires_at=expires_at, size_bytes=size_bytes
        )
        self._current_bytes += size_bytes
        self._items.move_to_end(key, last=True)
        self._evict_if_needed()

    def delete(self, key: str) -> None:
        """删除缓存条目。

        Args:
            key: 缓存键。
        """
        item = self._items.pop(key, None)
        if item is not None:
            self._current_bytes -= item.size_bytes

    def clear(self) -> None:
        """清空缓存。"""
        self._items.clear()
        self._current_bytes = 0

    def snapshot_serializable(self) -> dict[str, Any]:
        """返回可 JSON 序列化的快照。

        跳过不可序列化的条目。
        """
        import json

        now = self._now()
        out: dict[str, Any] = {}
        for key, item in list(self._items.items()):
            if self._is_expired(item, now):
                continue
            try:
                json.dumps(item.value)
            except Exception:
                continue
            out[key] = item.value
        return out

    def load_serializable(self, data: dict[str, Any]) -> None:
        """从快照加载缓存数据。

        Args:
            data: 快照数据字典。
        """
        now = self._now()
        for k, v in data.items():
            size_bytes = _estimate_size(v)
            self._items[str(k)] = CacheItem(
                value=v, expires_at=now + self._ttl_seconds, size_bytes=size_bytes
            )
            self._current_bytes += size_bytes
        self._evict_if_needed()

    def get_stats(self) -> dict[str, Any]:
        """获取缓存统计信息。

        Returns:
            包含各项统计指标的字典。
        """
        return {
            "entries": len(self._items),
            "max_entries": self._max_entries,
            "current_bytes": self._current_bytes,
            "max_bytes": self._max_bytes,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expired": self.expired,
            "hit_rate": self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0.0,
        }
