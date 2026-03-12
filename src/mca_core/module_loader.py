from __future__ import annotations
import importlib.util
import os
import sys
from typing import Optional


class ModuleLoader:
    def __init__(self, base_dir: str) -> None:
        self.base_dir = base_dir

    def load_module(self, name: str, path: str):
        if not os.path.exists(path):
            return None
        spec = importlib.util.spec_from_file_location(name, path)
        if spec and spec.loader:
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            spec.loader.exec_module(module)
            return module
        return None

    def try_import(self, module_path: str, fallback_path: Optional[str] = None):
        try:
            return __import__(module_path, fromlist=["*"])
        except Exception:
            if fallback_path:
                return self.load_module(module_path.split(".")[-1], fallback_path)
            return None
