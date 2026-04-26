"""
统一配置管理模块

提供统一的配置管理，支持多配置源和优先级合并。

模块说明:
    本模块提供统一的配置管理，支持：
        - 多配置源（文件、环境变量、默认值）
        - 优先级合并
        - 配置热更新
        - 类型安全访问
    
    主要组件:
        - ConfigSource: 配置源抽象基类
        - FileConfigSource: 文件配置源
        - EnvironmentConfigSource: 环境变量配置源
        - DictConfigSource: 字典配置源
        - ConfigManager: 统一配置管理器
"""

from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

logger = logging.getLogger(__name__)

T = TypeVar("T")

MAX_CONFIG_SIZE = 1024 * 1024


class ConfigSource(ABC):
    """
    配置源抽象基类。
    
    定义配置源的通用接口。
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """配置源名称。"""
        pass
    
    @property
    def priority(self) -> int:
        """
        配置源优先级。
        
        数值越大优先级越高，会覆盖低优先级的配置。
        默认优先级为 0。
        """
        return 0
    
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值。
        
        Args:
            key: 配置键，支持点号分隔的路径（如 "ui.theme"）
            default: 默认值
            
        Returns:
            配置值
        """
        pass
    
    @abstractmethod
    def has(self, key: str) -> bool:
        """
        检查配置键是否存在。
        
        Args:
            key: 配置键
            
        Returns:
            如果存在返回 True
        """
        pass
    
    def reload(self) -> None:
        """重新加载配置（可选实现）。"""
        pass


class DictConfigSource(ConfigSource):
    """
    字典配置源。
    
    从内存字典读取配置，适合作为默认配置源。
    """
    
    def __init__(
        self,
        name: str,
        data: Dict[str, Any],
        priority: int = 0,
    ) -> None:
        self._name = name
        self._data = data
        self._priority = priority
    
    @property
    def name(self) -> str:
        return self._name
    
    @property
    def priority(self) -> int:
        return self._priority
    
    def get(self, key: str, default: Any = None) -> Any:
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def has(self, key: str) -> bool:
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return False
        return True
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值。"""
        keys = key.split(".")
        data = self._data
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value


class FileConfigSource(ConfigSource):
    """
    文件配置源。
    
    从 JSON 文件读取配置，支持热更新。
    """
    
    def __init__(
        self,
        file_path: Union[str, Path],
        priority: int = 10,
        watch: bool = False,
        on_change: Optional[Callable[[], None]] = None,
    ) -> None:
        self._file_path = Path(file_path)
        self._priority = priority
        self._watch = watch
        self._on_change = on_change
        self._data: Dict[str, Any] = {}
        self._mtime: float = 0.0
        self._load()
    
    @property
    def name(self) -> str:
        return f"file:{self._file_path}"
    
    @property
    def priority(self) -> int:
        return self._priority
    
    def _load(self) -> None:
        """加载配置文件。"""
        if not self._file_path.exists():
            self._data = {}
            return
        
        try:
            file_size = self._file_path.stat().st_size
            if file_size > MAX_CONFIG_SIZE:
                logger.warning(
                    "Config file too large: %s (%d bytes), skipping",
                    self._file_path,
                    file_size,
                )
                return
            
            with open(self._file_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
            
            self._mtime = self._file_path.stat().st_mtime
            logger.debug("Loaded config from %s", self._file_path)
            
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in config file %s: %s", self._file_path, e)
            self._data = {}
        except Exception as e:
            logger.error("Failed to load config from %s: %s", self._file_path, e)
            self._data = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        if self._watch:
            self._check_reload()
        
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    def has(self, key: str) -> bool:
        if self._watch:
            self._check_reload()
        
        keys = key.split(".")
        value = self._data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return False
        return True
    
    def _check_reload(self) -> None:
        """检查是否需要重新加载。"""
        try:
            mtime = self._file_path.stat().st_mtime
            if mtime > self._mtime:
                self._load()
                if self._on_change:
                    self._on_change()
        except Exception:
            pass
    
    def reload(self) -> None:
        """强制重新加载。"""
        self._load()
    
    def save(self) -> None:
        """保存配置到文件。"""
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._file_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            self._mtime = self._file_path.stat().st_mtime
        except Exception as e:
            logger.error("Failed to save config to %s: %s", self._file_path, e)
    
    def set(self, key: str, value: Any) -> None:
        """设置配置值。"""
        keys = key.split(".")
        data = self._data
        for k in keys[:-1]:
            if k not in data:
                data[k] = {}
            data = data[k]
        data[keys[-1]] = value


class EnvironmentConfigSource(ConfigSource):
    """
    环境变量配置源。
    
    从环境变量读取配置，支持前缀和类型转换。
    """
    
    def __init__(
        self,
        prefix: str = "MCA_",
        priority: int = 20,
    ) -> None:
        self._prefix = prefix.upper()
        self._priority = priority
    
    @property
    def name(self) -> str:
        return f"env:{self._prefix}"
    
    @property
    def priority(self) -> int:
        return self._priority
    
    def get(self, key: str, default: Any = None) -> Any:
        env_key = self._prefix + key.upper().replace(".", "_")
        value = os.environ.get(env_key)
        if value is None:
            return default
        
        if isinstance(default, bool):
            return value.lower() in ("true", "1", "yes", "on")
        elif isinstance(default, int):
            try:
                return int(value)
            except ValueError:
                return default
        elif isinstance(default, float):
            try:
                return float(value)
            except ValueError:
                return default
        elif isinstance(default, list):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value.split(",")
        
        return value
    
    def has(self, key: str) -> bool:
        env_key = self._prefix + key.upper().replace(".", "_")
        return env_key in os.environ


class ConfigManager:
    """
    统一配置管理器。
    
    支持多配置源和优先级合并，提供类型安全的配置访问。
    
    Attributes:
        _sources: 配置源列表（按优先级排序）
        _change_callbacks: 配置变更回调列表
    
    方法:
        - add_source: 添加配置源
        - get: 获取配置值
        - get_int: 获取整数配置
        - get_float: 获取浮点数配置
        - get_bool: 获取布尔配置
        - get_str: 获取字符串配置
        - get_list: 获取列表配置
        - has: 检查配置是否存在
        - set: 设置配置值
        - on_change: 注册变更回调
        - reload_all: 重新加载所有配置源
    
    Example:
        >>> manager = ConfigManager()
        >>> manager.add_source(DictConfigSource("defaults", {"ui.theme": "light"}))
        >>> manager.add_source(FileConfigSource("config.json"))
        >>> theme = manager.get("ui.theme", default="dark")
    """
    
    def __init__(self) -> None:
        self._sources: List[ConfigSource] = []
        self._change_callbacks: List[Callable[[str, Any, Any], None]] = []
        self._cache: Dict[str, Any] = {}
        self._cache_enabled: bool = True
    
    def add_source(self, source: ConfigSource) -> "ConfigManager":
        """
        添加配置源。
        
        配置源按优先级排序，高优先级的配置会覆盖低优先级的。
        
        Args:
            source: 配置源实例
            
        Returns:
            管理器实例（支持链式调用）
        """
        self._sources.append(source)
        self._sources.sort(key=lambda s: s.priority, reverse=True)
        self._cache.clear()
        return self
    
    def remove_source(self, name: str) -> bool:
        """
        移除配置源。
        
        Args:
            name: 配置源名称
            
        Returns:
            如果成功移除返回 True
        """
        for i, source in enumerate(self._sources):
            if source.name == name:
                del self._sources[i]
                self._cache.clear()
                return True
        return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值。
        
        按优先级从高到低查找配置源，返回第一个找到的值。
        
        Args:
            key: 配置键，支持点号分隔的路径
            default: 默认值
            
        Returns:
            配置值
        """
        if self._cache_enabled and key in self._cache:
            return self._cache[key]
        
        for source in self._sources:
            if source.has(key):
                value = source.get(key, default)
                if self._cache_enabled:
                    self._cache[key] = value
                return value
        
        return default
    
    def get_int(self, key: str, default: int = 0) -> int:
        """获取整数配置。"""
        value = self.get(key, default)
        try:
            return int(value)
        except (ValueError, TypeError):
            return default
    
    def get_float(self, key: str, default: float = 0.0) -> float:
        """获取浮点数配置。"""
        value = self.get(key, default)
        try:
            return float(value)
        except (ValueError, TypeError):
            return default
    
    def get_bool(self, key: str, default: bool = False) -> bool:
        """获取布尔配置。"""
        value = self.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)
    
    def get_str(self, key: str, default: str = "") -> str:
        """获取字符串配置。"""
        value = self.get(key, default)
        return str(value) if value is not None else default
    
    def get_list(self, key: str, default: Optional[List[Any]] = None) -> List[Any]:
        """获取列表配置。"""
        if default is None:
            default = []
        value = self.get(key, default)
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                return value.split(",")
        return default
    
    def has(self, key: str) -> bool:
        """检查配置是否存在。"""
        for source in self._sources:
            if source.has(key):
                return True
        return False
    
    def set(self, key: str, value: Any, source_name: Optional[str] = None) -> bool:
        """
        设置配置值。
        
        Args:
            key: 配置键
            value: 配置值
            source_name: 目标配置源名称（如果为 None 则写入第一个可写源）
            
        Returns:
            如果成功设置返回 True
        """
        target: Optional[ConfigSource] = None
        
        if source_name:
            for source in self._sources:
                if source.name == source_name:
                    target = source
                    break
        else:
            for source in self._sources:
                if isinstance(source, (DictConfigSource, FileConfigSource)):
                    target = source
                    break
        
        if target is None:
            logger.warning("No writable config source found for key: %s", key)
            return False
        
        old_value = self.get(key)
        
        if isinstance(target, DictConfigSource):
            target.set(key, value)
        elif isinstance(target, FileConfigSource):
            target.set(key, value)
        else:
            return False
        
        if self._cache_enabled:
            self._cache[key] = value
        
        self._notify_change(key, old_value, value)
        return True
    
    def _notify_change(self, key: str, old_value: Any, new_value: Any) -> None:
        """通知配置变更。"""
        for callback in self._change_callbacks:
            try:
                callback(key, old_value, new_value)
            except Exception as e:
                logger.warning("Config change callback failed: %s", e)
    
    def on_change(self, callback: Callable[[str, Any, Any], None]) -> Callable[[], None]:
        """
        注册配置变更回调。
        
        Args:
            callback: 回调函数，接收 (key, old_value, new_value) 参数
            
        Returns:
            取消注册的函数
        """
        self._change_callbacks.append(callback)
        
        def unsubscribe() -> None:
            if callback in self._change_callbacks:
                self._change_callbacks.remove(callback)
        
        return unsubscribe
    
    def reload_all(self) -> None:
        """重新加载所有配置源。"""
        self._cache.clear()
        for source in self._sources:
            source.reload()
    
    def clear_cache(self) -> None:
        """清除配置缓存。"""
        self._cache.clear()
    
    def get_all_keys(self) -> List[str]:
        """
        获取所有配置键。
        
        Returns:
            配置键列表
        """
        keys: set = set()
        
        def extract_keys(data: Dict[str, Any], prefix: str = "") -> None:
            for k, v in data.items():
                full_key = f"{prefix}.{k}" if prefix else k
                if isinstance(v, dict):
                    extract_keys(v, full_key)
                else:
                    keys.add(full_key)
        
        for source in self._sources:
            if isinstance(source, DictConfigSource):
                extract_keys(source._data)
            elif isinstance(source, FileConfigSource):
                extract_keys(source._data)
        
        return list(keys)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        将所有配置导出为字典。
        
        Returns:
            配置字典
        """
        result: Dict[str, Any] = {}
        
        for key in self.get_all_keys():
            result[key] = self.get(key)
        
        return result


_global_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    """
    获取全局配置管理器实例。
    
    Returns:
        全局 ConfigManager 实例
    """
    global _global_config_manager
    if _global_config_manager is None:
        _global_config_manager = ConfigManager()
    return _global_config_manager


def reset_config_manager() -> None:
    """重置全局配置管理器（仅用于测试）。"""
    global _global_config_manager
    _global_config_manager = None
