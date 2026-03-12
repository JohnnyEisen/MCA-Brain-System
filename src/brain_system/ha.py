"""高可用模块。

提供基于 Redis 的 Leader 选举机制。

V-012 Fix: 增强Redis连接安全性
- 添加SSL/TLS支持
- 添加连接验证
- 添加超时控制
"""
from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse, parse_qs


_logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LeaderElectionConfig:
    """Leader 选举配置。

    Attributes:
        enabled: 是否启用 Leader 选举。
        redis_url: Redis 连接 URL。
        lock_key: 锁键名。
        ttl_seconds: 锁超时时间（秒）。
        renew_interval_seconds: 续期间隔（秒）。
        ssl_cert_reqs: SSL证书验证要求 ('required', 'optional', 'none')
        connection_timeout: 连接超时（秒）
        socket_timeout: Socket超时（秒）
    """

    enabled: bool = False
    redis_url: str = "redis://localhost:6379/0"
    lock_key: str = "brain:leader"
    ttl_seconds: int = 10
    renew_interval_seconds: float = 3.0
    ssl_cert_reqs: str = "required"
    connection_timeout: float = 5.0
    socket_timeout: float = 5.0


class RedisConnectionError(RuntimeError):
    """Redis连接错误"""
    pass


def _validate_redis_url(url: str) -> dict:
    """验证并解析Redis URL，提取安全配置。

    Args:
        url: Redis连接URL

    Returns:
        解析后的连接参数字典

    Raises:
        RedisConnectionError: URL格式无效或不安全
    """
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise RedisConnectionError(f"无效的Redis URL格式: {e}") from e

    params = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 6379,
        "db": int(parsed.path.lstrip("/")) if parsed.path else 0,
        "password": parsed.password,
    }

    if parsed.scheme == "rediss":
        params["ssl"] = True
    elif parsed.scheme not in ("redis",):
        raise RedisConnectionError(
            f"不支持的Redis协议: {parsed.scheme}，仅支持 redis:// 或 rediss://"
        )

    query_params = parse_qs(parsed.query)
    if "ssl_cert_reqs" in query_params:
        params["ssl_cert_reqs"] = query_params["ssl_cert_reqs"][0]

    return params


class LeaderElector:
    """基于 Redis 分布式锁的 Leader 选举。

    用于让一个实例承担"主控职责"（如写入外部状态、触发热升级）。
    可替换为 etcd/ZooKeeper 等其他实现。

    V-012 Fix: 增强连接安全性
    - 支持SSL/TLS连接
    - 连接超时控制
    - 连接健康检查

    Attributes:
        cfg: 选举配置。
    """

    def __init__(self, cfg: LeaderElectionConfig) -> None:
        """初始化 Leader 选举器。

        Args:
            cfg: 选举配置。

        Raises:
            RuntimeError: 未安装 redis 客户端。
            RedisConnectionError: 连接验证失败。
        """
        self.cfg = cfg
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._is_leader: bool = False
        self._last_error: str = ""

        try:
            import redis  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "未安装 redis 客户端，安装: pip install 'brain-system[ha]'"
            ) from e

        conn_params = _validate_redis_url(cfg.redis_url)

        ssl_cert_reqs = cfg.ssl_cert_reqs
        if "ssl_cert_reqs" in conn_params:
            ssl_cert_reqs = conn_params.pop("ssl_cert_reqs")

        if conn_params.get("ssl") or ssl_cert_reqs != "none":
            cert_reqs_map = {
                "required": "required",
                "optional": "optional",
                "none": None,
            }
            conn_params["ssl_cert_reqs"] = cert_reqs_map.get(ssl_cert_reqs, "required")

        conn_params["socket_timeout"] = cfg.socket_timeout
        conn_params["socket_connect_timeout"] = cfg.connection_timeout

        try:
            self._redis = redis.Redis(**conn_params)
            self._redis.ping()
            _logger.info("Redis连接成功: %s:%d", conn_params["host"], conn_params["port"])
        except redis.ConnectionError as e:
            raise RedisConnectionError(
                f"无法连接Redis服务器: {conn_params['host']}:{conn_params['port']}"
            ) from e
        except redis.AuthenticationError as e:
            raise RedisConnectionError(
                "Redis认证失败，请检查密码配置"
            ) from e
        except Exception as e:
            raise RedisConnectionError(
                f"Redis连接验证失败: {type(e).__name__}"
            ) from e

        self._lock = self._redis.lock(cfg.lock_key, timeout=cfg.ttl_seconds)

    @property
    def is_leader(self) -> bool:
        """当前实例是否为 Leader。"""
        return self._is_leader

    def _check_connection(self) -> bool:
        """检查Redis连接是否健康"""
        try:
            self._redis.ping()
            return True
        except Exception:
            return False

    def start(self) -> None:
        """启动 Leader 选举。"""
        if not self.cfg.enabled or self._thread is not None:
            return

        def run() -> None:
            consecutive_errors = 0
            max_consecutive_errors = 3

            while not self._stop.is_set():
                try:
                    if not self._check_connection():
                        raise ConnectionError("Redis连接不可用")

                    if not self._is_leader:
                        acquired = self._lock.acquire(blocking=False)
                        self._is_leader = bool(acquired)
                        if self._is_leader:
                            _logger.info("Leader 选举成功")
                            consecutive_errors = 0
                    else:
                        try:
                            self._lock.extend(self.cfg.ttl_seconds)
                            consecutive_errors = 0
                        except Exception:
                            self._is_leader = False
                            _logger.warning("Leader 锁续期失败，放弃Leader身份")

                except Exception as e:
                    consecutive_errors += 1
                    error_msg = f"{type(e).__name__}"
                    
                    if error_msg != self._last_error:
                        _logger.warning(
                            "Leader选举遇到错误 (%d/%d): %s",
                            consecutive_errors, max_consecutive_errors, error_msg
                        )
                        self._last_error = error_msg

                    if consecutive_errors >= max_consecutive_errors:
                        self._is_leader = False
                        _logger.error(
                            "连续%d次错误，暂停Leader选举尝试",
                            consecutive_errors
                        )

                time.sleep(float(self.cfg.renew_interval_seconds))

        self._thread = threading.Thread(target=run, daemon=True, name="LeaderElector")
        self._thread.start()

    def stop(self) -> None:
        """停止 Leader 选举并释放锁。"""
        self._stop.set()
        try:
            if self._is_leader:
                self._lock.release()
                _logger.info("已释放Leader锁")
        except Exception:
            pass
        self._is_leader = False
