import logging
from typing import Optional
from config.app_config import AppConfig

logger = logging.getLogger(__name__)

class ConfigService:
    """负责配置的加载、保存和状态管理。"""

    def __init__(self, config_path: str):
        self.config_path = config_path
        self._config: Optional[AppConfig] = None
        self.load()

    def load(self):
        try:
            self._config = AppConfig.load(self.config_path)
        except Exception:
            logger.exception("Failed to load config, using default")
            self._config = AppConfig()

    def save(self):
        try:
            if self._config:
                self._config.save(self.config_path)
        except Exception:
            logger.exception("Failed to save config")

    @property
    def config(self) -> "AppConfig":
        if self._config is None:
            self.load()
        # Type checker guarantee: _config is set after load()
        assert self._config is not None
        return self._config

    def get_scroll_sensitivity(self) -> int:
        val = self.config.scroll_sensitivity
        return val if isinstance(val, int) and val > 0 else 3 # Default fallback

    def set_scroll_sensitivity(self, value: int):
        self.config.scroll_sensitivity = value

    def get_highlight_size_limit(self) -> int:
        val = self.config.highlight_size_limit
        return val if isinstance(val, int) and val > 0 else 500 # Default fallback

    def set_highlight_size_limit(self, value: int):
        self.config.highlight_size_limit = value
