from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class LeaderElectionConfig:
    enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"
    lock_key: str = "brain:leader"
    ttl_seconds: int = 10
    renew_interval_seconds: float = 3.0


class LeaderElector:
    """基于 Redis 分布式锁的 Leader 选举（可选）。

    说明：
    - 这是生产常见做法之一；你也可以替换为 etcd/ZooKeeper。
    - 该实现用于让一个实例承担“主控职责”（例如写入外部状态/触发热升级）。
    """

    def __init__(self, cfg: LeaderElectionConfig):
        self.cfg = cfg
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._is_leader = False

        try:
            import redis  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("未安装 redis 客户端，安装: pip install 'brain-system[ha]'") from e

        self._redis = redis.Redis.from_url(cfg.redis_url)
        self._lock = self._redis.lock(cfg.lock_key, timeout=cfg.ttl_seconds)

    @property
    def is_leader(self) -> bool:
        return self._is_leader

    def start(self) -> None:
        if not self.cfg.enabled or self._thread is not None:
            return

        def run() -> None:
            while not self._stop.is_set():
                try:
                    if not self._is_leader:
                        acquired = self._lock.acquire(blocking=False)
                        self._is_leader = bool(acquired)
                        if self._is_leader:
                            logging.info("Leader 选举成功")
                    else:
                        try:
                            self._lock.extend(self.cfg.ttl_seconds)
                        except Exception:
                            self._is_leader = False
                except Exception:
                    self._is_leader = False

                time.sleep(float(self.cfg.renew_interval_seconds))

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        try:
            if self._is_leader:
                self._lock.release()
        except Exception:
            pass
        self._is_leader = False
