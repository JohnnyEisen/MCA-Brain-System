from __future__ import annotations
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict

from config.constants import DEFAULT_SCROLL_SENSITIVITY, HIGHLIGHT_SIZE_LIMIT


@dataclass
class AppConfig:
    scroll_sensitivity: int = DEFAULT_SCROLL_SENSITIVITY
    highlight_size_limit: int = HIGHLIGHT_SIZE_LIMIT
    max_history_items: int = 100
    auto_save_interval: int = 300
    theme: str = "light"
    enable_smart_learning: bool = True  # 新增设置项
    _mtime: float = field(default=0.0, repr=False)


    def _validate(self) -> None:
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
    def load(cls, config_file: str) -> "AppConfig":
        cfg = cls()
        if os.path.exists(config_file):
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                cfg.scroll_sensitivity = int(data.get("scroll_sensitivity", cfg.scroll_sensitivity))
                cfg.highlight_size_limit = int(data.get("highlight_size_limit", cfg.highlight_size_limit))
                cfg.max_history_items = int(data.get("max_history_items", cfg.max_history_items))
                cfg.auto_save_interval = int(data.get("auto_save_interval", cfg.auto_save_interval))
                cfg.theme = str(data.get("theme", cfg.theme))
                cfg.enable_smart_learning = bool(data.get("enable_smart_learning", cfg.enable_smart_learning))
                cfg._mtime = os.path.getmtime(config_file)
            except Exception:
                pass
        cfg._validate()
        return cfg

    def save(self, config_file: str) -> None:
        data: Dict[str, Any] = {
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

    def reload_if_changed(self, config_file: str) -> "AppConfig":
        try:
            mtime = os.path.getmtime(config_file)
            if mtime > self._mtime:
                return self.load(config_file)
        except Exception:
            pass
        return self
