from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Type

from .dlc import BrainDLC


def iter_dlc_files(search_paths: Sequence[str]) -> List[Path]:
    files: List[Path] = []
    for search_path in search_paths:
        path = Path(search_path).expanduser().resolve()
        if not path.exists() or not path.is_dir():
            continue
        files.extend(sorted(p for p in path.glob("*.py") if p.is_file()))
    return files


def load_dlc_classes_from_file(file_path: Path) -> List[Type[BrainDLC]]:
    """从文件加载 DLC 子类（只返回类，不实例化）。"""

    module_name = f"brain_dlc_{file_path.stem}"
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        return []

    module = importlib.util.module_from_spec(spec)
    sys.modules[module.__name__] = module
    spec.loader.exec_module(module)

    classes: List[Type[BrainDLC]] = []
    for _, obj in vars(module).items():
        if inspect.isclass(obj) and issubclass(obj, BrainDLC) and obj is not BrainDLC:
            classes.append(obj)
    return classes
