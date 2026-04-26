"""LRU + TTL 缓存模块。

提供带时间到期的最近最少使用缓存实现。
"""
from __future__ import annotations

import sys
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

_SIZE_ESTIMATE_CACHE: dict[int, int] = {}
_SIZE_CACHE_MAX = 1000


def _estimate_size(obj: Any) -> int:
    """估算对象的内存大小（字节）。
    
    使用采样策略平衡精度和性能：
    - 小型对象：精确计算
    - 大型对象：采样估算
    """
    obj_id = id(obj)
    if obj_id in _SIZE_ESTIMATE_CACHE:
        return _SIZE_ESTIMATE_CACHE[obj_id]
    
    if isinstance(obj, (str, bytes)):
        result = sys.getsizeof(obj)
    elif isinstance(obj, (int, float, bool, type(None))):
        result = sys.getsizeof(obj)
    elif isinstance(obj, (list, tuple)):
        base_size = sys.getsizeof(obj)
        length = len(obj)
        if length == 0:
            result = base_size
        elif length <= 20:
            result = base_size + sum(_estimate_size(item) for item in obj)
        else:
            sample_size = min(length, 20)
            step = max(1, length // sample_size)
            sample_sum = sum(_estimate_size(obj[i]) for i in range(0, length, step))
            result = base_size + (sample_sum * length // sample_size)
    elif isinstance(obj, dict):
        base_size = sys.getsizeof(obj)
        length = len(obj)
        if length == 0:
            result = base_size
        elif length <= 20:
            result = base_size + sum(_estimate_size(k) + _estimate_size(v) for k, v in obj.items())
        else:
            items = list(obj.items())
            step = max(1, length // 20)
            sample_sum = sum(
                _estimate_size(items[i][0]) + _estimate_size(items[i][1])
                for i in range(0, length, step)
            )
            result = base_size + (sample_sum * length // (length // step))
    elif isinstance(obj, (set, frozenset)):
        base_size = sys.getsizeof(obj)
        length = len(obj)
        if length == 0:
            result = base_size
        elif length <= 20:
            result = base_size + sum(_estimate_size(item) for item in obj)
        else:
            items = list(obj)
            step = max(1, length // 20)
            sample_sum = sum(_estimate_size(items[i]) for i in range(0, length, step))
            result = base_size + (sample_sum * length // (length // step))
    else:
        try:
            result = sys.getsizeof(obj)
        except Exception:
            result = 1024
    
    if len(_SIZE_ESTIMATE_CACHE) >= _SIZE_CACHE_MAX:
        _SIZE_ESTIMATE_CACHE.pop(next(iter(_SIZE_ESTIMATE_CACHE)))
    _SIZE_ESTIMATE_CACHE[obj_id] = result
    
    return result


@dataclass(slots=True)
class CacheItem:
    """缓存项：存储值和过期时间。

    Attributes:
        value: 缓存的值。
        expires_at: 过期时间戳（秒）。
        size_bytes: 估算的字节大小。
        access_count: 访问次数（用于动态 TTL）。
    """

    value: Any
    expires_at: float
    size_bytes: int = 0
    access_count: int = 0


class LruTtlCache:
    """LRU + TTL 缓存，支持动态 TTL。

    特性：
    - max_entries: 最大条目数
    - max_bytes: 最大字节数（可选）
    - ttl_seconds: 每个条目的存活时间
    - dynamic_ttl: 根据访问频率动态调整 TTL
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
        dynamic_ttl: bool = True,
        dynamic_ttl_multiplier: float = 2.0,
    ) -> None:
        """初始化缓存。

        Args:
            max_entries: 最大条目数，必须大于 0。
            ttl_seconds: 条目存活时间（秒），必须大于 0。
            max_bytes: 最大字节数（可选），None 表示不限制。
            dynamic_ttl: 是否启用动态 TTL（根据访问频率调整）。
            dynamic_ttl_multiplier: 动态 TTL 最大倍数。

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
        self._dynamic_ttl: bool = dynamic_ttl
        self._dynamic_ttl_multiplier: float = dynamic_ttl_multiplier
        self._items: OrderedDict[str, CacheItem] = OrderedDict()
        self._current_bytes: int = 0
        self._write_ops: int = 0

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

        # 定期执行小预算全表过期清理，避免仅清理队首导致的过期项滞留。
        if self._write_ops and (self._write_ops & 63) == 0:
            self._purge_expired_sample(budget=64)

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

    def _purge_expired_sample(self, budget: int = 64) -> None:
        """有限预算扫描过期条目。"""
        if not self._items or budget <= 0:
            return

        now = self._now()
        removed = 0
        for key, item in list(self._items.items()):
            if self._is_expired(item, now):
                self._items.pop(key, None)
                self._current_bytes -= item.size_bytes
                self.expired += 1
                removed += 1
                if removed >= budget:
                    break

    def get(self, key: str) -> Any:
        """获取缓存值，支持动态 TTL。

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

        # 动态 TTL：增加访问计数
        if self._dynamic_ttl:
            item.access_count += 1
            ttl_boost = min(item.access_count / 10.0, self._dynamic_ttl_multiplier - 1.0)
            item.expires_at = now + (self._ttl_seconds * (1.0 + ttl_boost))

        self._items.move_to_end(key, last=True)
        self.hits += 1
        return item.value

    def set(self, key: str, value: Any, ttl: float | None = None) -> None:
        """设置缓存值，支持动态 TTL。

        Args:
            key: 缓存键。
            value: 缓存值。
            ttl: 可选的自定义 TTL（秒），None 使用默认值。
        """
        # 如果键已存在，先减去旧值的大小
        if key in self._items:
            old_item = self._items[key]
            self._current_bytes -= old_item.size_bytes

        # 估算新值大小
        size_bytes = _estimate_size(value)
        
        # 计算过期时间
        base_ttl = ttl if ttl is not None else self._ttl_seconds
        expires_at = self._now() + base_ttl

        self._items[key] = CacheItem(
            value=value, expires_at=expires_at, size_bytes=size_bytes, access_count=0
        )
        self._current_bytes += size_bytes
        self._items.move_to_end(key, last=True)
        self._write_ops += 1
        self._evict_if_needed()
    
    def refresh_ttl(self, key: str) -> bool:
        """刷新条目的 TTL。

        Args:
            key: 缓存键。

        Returns:
            是否成功刷新（条目存在且未过期）。
        """
        now = self._now()
        item = self._items.get(key)
        if item is None or self._is_expired(item, now):
            return False
        
        # 动态 TTL：根据访问频率延长过期时间
        if self._dynamic_ttl:
            multiplier = 1.0 + min(item.access_count / 10.0, self._dynamic_ttl_multiplier - 1.0)
            item.expires_at = now + (self._ttl_seconds * multiplier)
        else:
            item.expires_at = now + self._ttl_seconds
        
        return True

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
