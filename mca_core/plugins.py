"""Plugin registry for extensibility."""
from __future__ import annotations
import os
import importlib.util
import logging
from typing import Callable, List

logger = logging.getLogger(__name__)

class PluginRegistry:
    def __init__(self):
        self._plugins: List[Callable] = []

    def register(self, plugin: Callable):
        self._plugins.append(plugin)

    def list(self):
        return list(self._plugins)

    def load_from_directory(self, plugin_dir: str):
        """Discovers and loads plugins from a directory.
        
        Expected structure:
        - plugin_script.py
        - must define a 'plugin_entry(analyzer)' function.
        """
        if not os.path.exists(plugin_dir):
            return

        for filename in os.listdir(plugin_dir):
            if filename.endswith(".py") and not filename.startswith("_"):
                filepath = os.path.join(plugin_dir, filename)
                try:
                    spec = importlib.util.spec_from_file_location(filename[:-3], filepath)
                    if spec and spec.loader:
                        mod = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(mod)
                        if hasattr(mod, "plugin_entry"):
                            self.register(mod.plugin_entry)
                            logger.info(f"Loaded plugin: {filename}")
                        else:
                            logger.debug(f"Skipping {filename}: no 'plugin_entry' found.")
                except Exception as e:
                    logger.error(f"Failed to load plugin {filename}: {e}")
