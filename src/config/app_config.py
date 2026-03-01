"""Application Config Module - SECURE VERSION

Define application configuration data classes and load/save logic.
Fix V-004: JSON DoS vulnerability
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field

from typing import Any

from config.constants import DEFAULT_SCROLL_SENSITIVITY, HIGHLIGHT_SIZE_LIMIT

logger = logging.getLogger(__name__)

# ============================================================
# V-004 Fix: JSON DoS Protection
# ============================================================
MAX_CONFIG_SIZE = 1024 * 1024  # 1MB config file size limit


@dataclass
class AppConfig:
    """Application configuration data class.
    
    Attributes:
        scroll_sensitivity: Scroll sensitivity.
        highlight_size_limit: Highlight display size limit.
        max_history_items: Maximum history entries.
        auto_save_interval: Auto-save interval (seconds).
        theme: UI theme.
        enable_smart_learning: Enable smart learning.
    """
    
    scroll_sensitivity: int = DEFAULT_SCROLL_SENSITIVITY
    highlight_size_limit: int = HIGHLIGHT_SIZE_LIMIT
    max_history_items: int = 100
    auto_save_interval: int = 300
    theme: str = "light"
    enable_smart_learning: bool = True
    _mtime: float = field(default=0.0, repr=False)
    
    def _validate(self) -> None:
        """Validate and fix configuration values."""
        try:
            self.scroll_sensitivity = int(self.scroll_sensitivity)
        except Exception:
            self.scroll_sensitivity = DEFAULT_SCROLL_SENSITIVITY
        if self.scroll_sensitivity <= 0:
            self.scroll_sensitivity = DEFAULT_SCROLL_SENSITIVITY
        
        try:
            self.highlight_size_limit = int(self.highlight_size_limit)
        except Exception:
            self.highlight_size_limit = HIGHLIGHT_SIZE_LIMIT
        if self.highlight_size_limit <= 0:
            self.highlight_size_limit = HIGHLIGHT_SIZE_LIMIT
        
        try:
            self.max_history_items = int(self.max_history_items)
        except Exception:
            self.max_history_items = 100
        if self.max_history_items <= 0:
            self.max_history_items = 100
        
        try:
            self.auto_save_interval = int(self.auto_save_interval)
        except Exception:
            self.auto_save_interval = 300
        if self.auto_save_interval <= 0:
            self.auto_save_interval = 300
        
        if not isinstance(self.theme, str) or not self.theme:
            self.theme = "light"
        
        if not isinstance(self.enable_smart_learning, bool):
            self.enable_smart_learning = True
    
    @classmethod
    def load(cls, config_file: str) -> AppConfig:
        """Load configuration from file.
        
        Args:
            config_file: Configuration file path.
            
        Returns:
            Loaded configuration object.
        """
        cfg = cls()
        if os.path.exists(config_file):
            # V-004 Fix: Check config file size
            try:
                file_size = os.path.getsize(config_file)
                if file_size > MAX_CONFIG_SIZE:
                    logger.warning(
                        f"Config file too large: {file_size} bytes (max: {MAX_CONFIG_SIZE}), using defaults"
                    )
                    return cfg
            except Exception:
                pass
            
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                try:
                    cfg.scroll_sensitivity = int(
                        data.get("scroll_sensitivity", cfg.scroll_sensitivity)
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(
                        "Invalid scroll_sensitivity in config: %s, using default", e
                    )
                
                try:
                    cfg.highlight_size_limit = int(
                        data.get("highlight_size_limit", cfg.highlight_size_limit)
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(
                        "Invalid highlight_size_limit in config: %s, using default", e
                    )
                
                try:
                    cfg.max_history_items = int(
                        data.get("max_history_items", cfg.max_history_items)
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(
                        "Invalid max_history_items in config: %s, using default", e
                    )
                
                try:
                    cfg.auto_save_interval = int(
                        data.get("auto_save_interval", cfg.auto_save_interval)
                    )
                except (ValueError, TypeError) as e:
                    logger.warning(
                        "Invalid auto_save_interval in config: %s, using default", e
                    )
                
                cfg.theme = str(data.get("theme", cfg.theme))
                cfg.enable_smart_learning = bool(
                    data.get("enable_smart_learning", cfg.enable_smart_learning)
                )
                
                try:
                    cfg._mtime = os.path.getmtime(config_file)
                except Exception:
                    pass
                    
            except Exception as e:
                logger.error("Failed to load config from %s: %s", config_file, e)
        
        cfg._validate()
        return cfg
    
    def save(self, config_file: str) -> None:
        """Save configuration to file.
        
        Args:
            config_file: Configuration file path.
        """
        data: dict[str, Any] = {
            "scroll_sensitivity": int(self.scroll_sensitivity),
            "highlight_size_limit": int(self.highlight_size_limit),
            "max_history_items": int(self.max_history_items),
            "auto_save_interval": int(self.auto_save_interval),
            "theme": self.theme,
            "enable_smart_learning": self.enable_smart_learning,
        }
        with open(config_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        try:
            self._mtime = os.path.getmtime(config_file)
        except Exception:
            pass
    
    def reload_if_changed(self, config_file: str) -> AppConfig:
        """Reload configuration if file has changed.
        
        Args:
            config_file: Configuration file path.
            
        Returns:
            Current or reloaded configuration.
        """
        try:
            mtime = os.path.getmtime(config_file)
            if mtime > self._mtime:
                return self.load(config_file)
        except Exception:
            pass
        return self
