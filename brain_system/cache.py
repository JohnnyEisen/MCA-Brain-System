from __future__ import annotations

import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(slots=True)
class CacheItem:
    value: Any
    expires_at: float


class LruTtlCache:
    """LRU + TTL cache.

    - max_entries: 最大条目数
    - ttl_seconds: 每个条目的存活时间

    说明：
    - get() 会刷新 LRU 顺序
    - 过期条目会在访问/写入时惰性清理
    """

    def __init__(self, *, max_entries: int, ttl_seconds: float):
        if max_entries <= 0:
            raise ValueError("max_entries must be > 0")
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")

        self._max_entries = int(max_entries)
        self._ttl_seconds = float(ttl_seconds)
        self._items: OrderedDict[str, CacheItem] = OrderedDict()

        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expired = 0

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def ttl_seconds(self) -> float:
        return self._ttl_seconds

    def __len__(self) -> int:
        return len(self._items)

    def set_limits(self, *, max_entries: Optional[int] = None, ttl_seconds: Optional[float] = None) -> None:
        if max_entries is not None:
            if max_entries <= 0:
                raise ValueError("max_entries must be > 0")
            self._max_entries = int(max_entries)
        if ttl_seconds is not None:
            if ttl_seconds <= 0:
                raise ValueError("ttl_seconds must be > 0")
            self._ttl_seconds = float(ttl_seconds)

        self._evict_if_needed()

    def _now(self) -> float:
        return time.time()

    def _is_expired(self, item: CacheItem, now: float) -> bool:
        return item.expires_at <= now

    def _purge_expired_front(self) -> None:
        # 只从最旧一侧开始清理，避免每次 O(n)
        now = self._now()
        keys_to_delete = []
        for key, item in self._items.items():
            if self._is_expired(item, now):
                keys_to_delete.append(key)
            else:
                break
        for key in keys_to_delete:
            self._items.pop(key, None)
            self.expired += 1

    def _evict_if_needed(self) -> None:
        self._purge_expired_front()
        while len(self._items) > self._max_entries:
            self._items.popitem(last=False)
            self.evictions += 1

    def get(self, key: str) -> Any:
        now = self._now()
        item = self._items.get(key)
        if item is None:
            self.misses += 1
            return None
        if self._is_expired(item, now):
            self._items.pop(key, None)
            self.expired += 1
            self.misses += 1
            return None

        self._items.move_to_end(key, last=True)
        self.hits += 1
        return item.value

    def set(self, key: str, value: Any) -> None:
        expires_at = self._now() + self._ttl_seconds
        self._items[key] = CacheItem(value=value, expires_at=expires_at)
        self._items.move_to_end(key, last=True)
        self._evict_if_needed()

    def delete(self, key: str) -> None:
        self._items.pop(key, None)

    def clear(self) -> None:
        self._items.clear()

    def snapshot_serializable(self) -> dict[str, Any]:
        """返回可 JSON 序列化的快照（跳过不可序列化项）。"""
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
        now = self._now()
        for k, v in data.items():
            self._items[str(k)] = CacheItem(value=v, expires_at=now + self._ttl_seconds)
        self._evict_if_needed()
