"""
Brain Core 配置验证模块

提供 BrainCore 配置的验证和默认值管理。

模块说明:
    本模块从 brain_system/core.py 提取配置相关逻辑，
    提供独立的配置验证和默认值管理功能。
    
    主要组件:
        - DEFAULT_CONFIG: 默认配置字典
        - validate_config: 配置验证函数
        - ConfigValidator: 配置验证器类
"""

from __future__ import annotations

import json
import logging
import multiprocessing
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


AUTOTUNE_PROFILES = {"manual", "auto", "small_core", "large_core"}
ROUTING_STRATEGIES = {"balanced", "throughput", "latency", "legacy"}
SMALL_CORE_CPU_THRESHOLD = 8


def _normalize_autotune_profile(profile: Any) -> str:
    value = str(profile).strip().lower().replace("-", "_")
    if value in {"small", "smallcore"}:
        return "small_core"
    if value in {"large", "largecore"}:
        return "large_core"
    return value


def _normalize_routing_strategy(strategy: Any) -> str:
    value = str(strategy).strip().lower()
    if value not in ROUTING_STRATEGIES:
        return "balanced"
    return value


def _safe_int(
    value: Any,
    default: int,
    *,
    minimum: int,
    maximum: Optional[int] = None,
) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default

    if parsed < minimum:
        parsed = minimum
    if maximum is not None and parsed > maximum:
        parsed = maximum
    return parsed


def _resolve_executor_autotune(
    merged: Dict[str, Any],
    user_config: Dict[str, Any],
) -> Dict[str, Any]:
    """将自动调优档位解析为实际执行器参数。"""
    cpu_count = max(1, multiprocessing.cpu_count())
    requested_profile = _normalize_autotune_profile(
        merged.get("executor_autotune_profile", "auto")
    )
    if requested_profile not in AUTOTUNE_PROFILES:
        requested_profile = "manual"

    if requested_profile == "auto":
        resolved_profile = "small_core" if cpu_count <= SMALL_CORE_CPU_THRESHOLD else "large_core"
    else:
        resolved_profile = requested_profile

    merged["executor_autotune_profile"] = requested_profile
    merged["executor_autotune_resolved_profile"] = resolved_profile

    if resolved_profile == "manual":
        merged["executor_routing_strategy"] = _normalize_routing_strategy(
            merged.get("executor_routing_strategy", "balanced")
        )
        return merged

    is_small = resolved_profile == "small_core"
    suffix = "small_core" if is_small else "large_core"

    default_thread_pool: int = (
        min(max(cpu_count * 2, 4), 16) if is_small else min(cpu_count * 4, 64)
    )
    default_process_pool: int = (
        max(0, min(cpu_count // 2, 4)) if is_small else min(cpu_count, 16)
    )
    default_routing_strategy = "latency" if is_small else "throughput"
    default_payload_bytes: int = 131_072 if is_small else 524_288

    profile_int_defaults: Dict[str, int] = {
        "thread_pool_size": default_thread_pool,
        "process_pool_size": default_process_pool,
        "process_pool_payload_max_bytes": default_payload_bytes,
    }

    profile_str_defaults: Dict[str, str] = {
        "executor_routing_strategy": default_routing_strategy,
    }

    def pick_value(base_key: str) -> Any:
        profile_key = f"{base_key}_{suffix}"
        if profile_key in user_config:
            return user_config[profile_key]
        if base_key in user_config:
            return user_config[base_key]
        if base_key in profile_int_defaults:
            return merged.get(profile_key, profile_int_defaults[base_key])
        return merged.get(profile_key, profile_str_defaults[base_key])

    merged["thread_pool_size"] = _safe_int(
        pick_value("thread_pool_size"),
        int(default_thread_pool),
        minimum=1,
    )
    merged["process_pool_size"] = _safe_int(
        pick_value("process_pool_size"),
        int(default_process_pool),
        minimum=0,
        maximum=cpu_count,
    )
    merged["process_pool_payload_max_bytes"] = _safe_int(
        pick_value("process_pool_payload_max_bytes"),
        int(default_payload_bytes),
        minimum=1024,
    )
    merged["executor_routing_strategy"] = _normalize_routing_strategy(
        pick_value("executor_routing_strategy")
    )
    return merged


DEFAULT_CONFIG: Dict[str, Any] = {
    # 与 BrainCore 历史默认值保持一致，避免架构收敛时引入行为回归。
    "thread_pool_size": 50,
    "process_pool_size": multiprocessing.cpu_count(),
    "enable_disk_cache": True,
    "cache_size_mb": 256,
    "cache_max_entries": 10_000,
    "cache_ttl_seconds": 300,
    "log_level": "INFO",
    "log_json": False,
    "monitoring_interval": 5.0,
    "auto_load_dlcs": True,
    "dlc_search_paths": ["./dlcs"],
    "dlc_strict_dependency_check": True,
    
    "dlc_signature_required": False,
    "dlc_signature_verify_if_present": True,
    "dlc_public_key_pem_files": [],
    
    "enable_metrics": False,
    "enable_tracing": False,
    "service_name": "brain",
    
    "retry_max_attempts": 1,
    "retry_initial_delay_seconds": 0.2,
    "retry_max_delay_seconds": 5.0,
    "retry_backoff_multiplier": 2.0,
    "retry_jitter_ratio": 0.2,

    # 传统计算执行器调度
    "executor_autotune_profile": "auto",  # auto|manual|small_core|large_core
    "executor_autotune_resolved_profile": "manual",
    "executor_routing_strategy": "balanced",  # balanced|throughput|latency
    "cpu_task_prefixes": ["cpu_", "cpu_task", "thread_cpu_"],
    "io_task_prefixes": ["io_", "net_", "disk_"],
    "process_pool_payload_max_bytes": 262_144,
    "thread_pool_size_small_core": min(max(multiprocessing.cpu_count() * 2, 4), 16),
    "process_pool_size_small_core": max(0, min(multiprocessing.cpu_count() // 2, 4)),
    "executor_routing_strategy_small_core": "latency",
    "process_pool_payload_max_bytes_small_core": 131_072,
    "thread_pool_size_large_core": min(multiprocessing.cpu_count() * 4, 64),
    "process_pool_size_large_core": min(multiprocessing.cpu_count(), 16),
    "executor_routing_strategy_large_core": "throughput",
    "process_pool_payload_max_bytes_large_core": 524_288,
    
    "enable_config_watch": False,
    "config_source": "file",
    "config_poll_seconds": 1.0,
    "consul_host": "127.0.0.1",
    "consul_port": 8500,
    "consul_key_prefix": "brain/config",
    
    "leader_election_enabled": False,
    "redis_url": "redis://localhost:6379/0",
    "leader_lock_key": "brain:leader",
    "leader_ttl_seconds": 10,
    "leader_renew_interval_seconds": 3.0,
}


class ConfigValidator:
    """
    配置验证器。
    
    提供 BrainCore 配置的验证功能。
    
    方法:
        - validate: 验证配置并返回错误列表
        - apply_defaults: 应用默认值
        - merge: 合并用户配置和默认配置
    
    Example:
        >>> validator = ConfigValidator()
        >>> errors = validator.validate(user_config)
        >>> if errors:
        ...     print("配置错误:", errors)
    """
    
    VALID_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
    
    def __init__(self) -> None:
        self._errors: List[str] = []
    
    def validate(self, config: Dict[str, Any]) -> List[str]:
        """
        验证配置。
        
        Args:
            config: 配置字典
            
        Returns:
            错误消息列表，空列表表示验证通过
        """
        self._errors = []
        
        self._validate_cache_config(config)
        self._validate_retry_config(config)
        self._validate_pool_config(config)
        self._validate_log_config(config)
        self._validate_timeout_config(config)
        self._validate_leader_election_config(config)
        self._validate_executor_config(config)
        
        return self._errors
    
    def _validate_cache_config(self, config: Dict[str, Any]) -> None:
        """验证缓存配置。"""
        if "cache_max_entries" in config:
            val = config["cache_max_entries"]
            if not isinstance(val, int) or val <= 0:
                self._errors.append(
                    f"cache_max_entries must be a positive integer, got {val}"
                )
        
        if "cache_ttl_seconds" in config:
            val = config["cache_ttl_seconds"]
            if not isinstance(val, (int, float)) or val <= 0:
                self._errors.append(
                    f"cache_ttl_seconds must be a positive number, got {val}"
                )
        
        if "cache_size_mb" in config:
            val = config["cache_size_mb"]
            if not isinstance(val, int) or val <= 0:
                self._errors.append(
                    f"cache_size_mb must be a positive integer, got {val}"
                )
    
    def _validate_retry_config(self, config: Dict[str, Any]) -> None:
        """验证重试配置。"""
        if "retry_max_attempts" in config:
            val = config["retry_max_attempts"]
            if not isinstance(val, int) or val <= 0:
                self._errors.append(
                    f"retry_max_attempts must be a positive integer, got {val}"
                )
        
        if "retry_initial_delay_seconds" in config:
            val = config["retry_initial_delay_seconds"]
            if not isinstance(val, (int, float)) or val < 0:
                self._errors.append(
                    f"retry_initial_delay_seconds must be a non-negative number, got {val}"
                )
        
        if "retry_backoff_multiplier" in config:
            val = config["retry_backoff_multiplier"]
            if not isinstance(val, (int, float)) or val < 1.0:
                self._errors.append(
                    f"retry_backoff_multiplier must be >= 1.0, got {val}"
                )
    
    def _validate_pool_config(self, config: Dict[str, Any]) -> None:
        """验证线程池配置。"""
        if "thread_pool_size" in config:
            val = config["thread_pool_size"]
            if not isinstance(val, int) or val <= 0 or val > 1000:
                self._errors.append(
                    f"thread_pool_size must be between 1 and 1000, got {val}"
                )
        
        if "process_pool_size" in config:
            val = config["process_pool_size"]
            if not isinstance(val, int) or val < 0 or val > multiprocessing.cpu_count():
                self._errors.append(
                    f"process_pool_size must be between 0 and {multiprocessing.cpu_count()}, got {val}"
                )
    
    def _validate_log_config(self, config: Dict[str, Any]) -> None:
        """验证日志配置。"""
        if "log_level" in config:
            val = config["log_level"]
            if str(val).upper() not in self.VALID_LOG_LEVELS:
                self._errors.append(
                    f"log_level must be one of {self.VALID_LOG_LEVELS}, got {val}"
                )
    
    def _validate_timeout_config(self, config: Dict[str, Any]) -> None:
        """验证超时配置。"""
        if "task_default_timeout" in config:
            val = config["task_default_timeout"]
            if not isinstance(val, (int, float)) or val < 0:
                self._errors.append(
                    f"task_default_timeout must be a non-negative number, got {val}"
                )
        
        if "monitoring_interval" in config:
            val = config["monitoring_interval"]
            if not isinstance(val, (int, float)) or val <= 0:
                self._errors.append(
                    f"monitoring_interval must be a positive number, got {val}"
                )
    
    def _validate_leader_election_config(self, config: Dict[str, Any]) -> None:
        """验证 Leader 选举配置。"""
        if config.get("leader_election_enabled", False):
            redis_url = config.get("redis_url")
            if not redis_url or not isinstance(redis_url, str):
                self._errors.append(
                    "redis_url is required when leader_election_enabled is True"
                )

    def _validate_executor_config(self, config: Dict[str, Any]) -> None:
        """验证执行器调度配置。"""
        if "executor_autotune_profile" in config:
            val = _normalize_autotune_profile(config["executor_autotune_profile"])
            if val not in AUTOTUNE_PROFILES:
                self._errors.append(
                    "executor_autotune_profile must be one of ('auto', 'manual', 'small_core', 'large_core')"
                )

        if "executor_routing_strategy" in config:
            val = str(config["executor_routing_strategy"]).lower()
            if val not in ROUTING_STRATEGIES:
                self._errors.append(
                    f"executor_routing_strategy must be one of ('balanced', 'throughput', 'latency', 'legacy'), got {config['executor_routing_strategy']}"
                )

        for strategy_key in [
            "executor_routing_strategy_small_core",
            "executor_routing_strategy_large_core",
        ]:
            if strategy_key in config:
                val = str(config[strategy_key]).lower()
                if val not in ROUTING_STRATEGIES:
                    self._errors.append(
                        f"{strategy_key} must be one of ('balanced', 'throughput', 'latency', 'legacy'), got {config[strategy_key]}"
                    )

        if "cpu_task_prefixes" in config and not isinstance(config["cpu_task_prefixes"], list):
            self._errors.append("cpu_task_prefixes must be a list")

        if "io_task_prefixes" in config and not isinstance(config["io_task_prefixes"], list):
            self._errors.append("io_task_prefixes must be a list")

        if "process_pool_payload_max_bytes" in config:
            val = config["process_pool_payload_max_bytes"]
            if not isinstance(val, int) or val < 1024:
                self._errors.append(
                    f"process_pool_payload_max_bytes must be an integer >= 1024, got {val}"
                )

        for payload_key in [
            "process_pool_payload_max_bytes_small_core",
            "process_pool_payload_max_bytes_large_core",
        ]:
            if payload_key in config:
                val = config[payload_key]
                if not isinstance(val, int) or val < 1024:
                    self._errors.append(
                        f"{payload_key} must be an integer >= 1024, got {val}"
                    )
    
    @staticmethod
    def apply_defaults(config: Dict[str, Any]) -> Dict[str, Any]:
        """
        应用默认值。
        
        Args:
            config: 用户配置字典
            
        Returns:
            合并后的配置字典
        """
        result = dict(DEFAULT_CONFIG)
        result.update(config)
        return result
    
    @staticmethod
    def merge(
        base: Dict[str, Any],
        override: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        合并配置。
        
        Args:
            base: 基础配置
            override: 覆盖配置
            
        Returns:
            合并后的配置
        """
        result = dict(base)
        result.update(override)
        return result


def validate_config(config: Dict[str, Any]) -> List[str]:
    """
    验证配置的便捷函数。
    
    Args:
        config: 配置字典
        
    Returns:
        错误消息列表
    """
    validator = ConfigValidator()
    return validator.validate(config)


def get_default_config() -> Dict[str, Any]:
    """
    获取默认配置的便捷函数。
    
    Returns:
        默认配置字典的副本
    """
    return dict(DEFAULT_CONFIG)


def load_config_file(config_path: Optional[str]) -> Dict[str, Any]:
    """加载配置文件并返回字典。

    读取失败、文件不存在或根节点不是字典时，返回空字典。
    """
    if not config_path:
        return {}

    if not os.path.exists(config_path):
        return {}

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.warning("加载配置文件失败: %s", e)
        return {}

    if not isinstance(data, dict):
        logger.warning("配置文件根节点必须是对象(dict): %s", config_path)
        return {}

    return data


def build_config(
    config_path: Optional[str],
    *,
    base_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """构建运行时配置。

    合并优先级：`base_config` 或默认配置 < 配置文件。
    """
    merged = dict(base_config) if base_config is not None else get_default_config()
    user_config = load_config_file(config_path)
    merged.update(user_config)
    return _resolve_executor_autotune(merged, user_config)
