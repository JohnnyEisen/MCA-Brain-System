"""
配置服务模块

负责应用配置的加载、保存和状态管理。

类说明:
    - ConfigService: 配置管理服务，封装配置文件的读写操作
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from config.app_config import AppConfig

logger = logging.getLogger(__name__)


class ConfigService:
    """
    配置管理服务。
    
    负责应用配置的加载、保存和状态管理。
    提供类型安全的配置访问接口。
    
    Attributes:
        config_path: 配置文件路径
        _config: 配置对象实例
    
    方法:
        - load: 加载配置文件
        - save: 保存配置文件
        - get_scroll_sensitivity: 获取滚动灵敏度
        - set_scroll_sensitivity: 设置滚动灵敏度
        - get_highlight_size_limit: 获取高亮大小限制
        - set_highlight_size_limit: 设置高亮大小限制
    """

    def __init__(self, config_path: str) -> None:
        """
        初始化配置服务。
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path: str = config_path
        self._config: Optional[AppConfig] = None
        self.load()

    def load(self) -> None:
        """加载配置文件。"""
        try:
            from config.app_config import AppConfig
            self._config = AppConfig.load(self.config_path)
        except Exception:
            logger.exception("Failed to load config, using default")
            from config.app_config import AppConfig
            self._config = AppConfig()

    def save(self) -> None:
        """保存配置文件。"""
        try:
            if self._config:
                self._config.save(self.config_path)
        except Exception:
            logger.exception("Failed to save config")

    @property
    def config(self) -> AppConfig:
        """
        获取配置对象。
        
        Returns:
            AppConfig 配置对象实例
        """
        if self._config is None:
            self.load()
        assert self._config is not None
        return self._config

    def get_scroll_sensitivity(self) -> int:
        """
        获取滚动灵敏度。
        
        Returns:
            滚动灵敏度值，默认为 3
        """
        val = self.config.scroll_sensitivity
        return val if isinstance(val, int) and val > 0 else 3

    def set_scroll_sensitivity(self, value: int) -> None:
        """
        设置滚动灵敏度。
        
        Args:
            value: 新的滚动灵敏度值
        """
        self.config.scroll_sensitivity = value

    def get_highlight_size_limit(self) -> int:
        """
        获取高亮大小限制。
        
        Returns:
            高亮大小限制值，默认为 500
        """
        val = self.config.highlight_size_limit
        return val if isinstance(val, int) and val > 0 else 500

    def set_highlight_size_limit(self, value: int) -> None:
        """
        设置高亮大小限制。
        
        Args:
            value: 新的高亮大小限制值
        """
        self.config.highlight_size_limit = value
