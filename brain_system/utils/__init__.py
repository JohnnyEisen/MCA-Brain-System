"""utils: 辅助工具集（可选导入/设备抽象/张量占位）。"""
from __future__ import annotations

import importlib
from typing import Any, Dict, Optional
import logging


class MissingOptionalDependency:
    """缺失依赖占位符，属性访问时抛出异常。"""
    def __init__(self, name: str, install_hint: str):
        self._name = name
        self._hint = install_hint

    def __getattr__(self, item):
        raise ImportError(f"缺少可选依赖 {self._name}，{self._hint}")


_OPTIONAL_IMPORT_CACHE: Dict[str, Any] = {}

def optional_import(module_name: str) -> Any:
    """运行时可选导入，失败返回 None。"""
    if module_name in _OPTIONAL_IMPORT_CACHE:
        return _OPTIONAL_IMPORT_CACHE[module_name]
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        mod = None
    _OPTIONAL_IMPORT_CACHE[module_name] = mod
    return mod

def require_optional(mod: Any, name: str, install_hint: str) -> Any:
    """强校验：模块必须存在，否则抛出 ImportError。"""
    if mod is None:
        raise ImportError(f"缺少可选依赖 {name}，{install_hint}")
    return mod


class Device:
    """设备抽象基类。"""
    def __init__(self, device_id: str):
        self.device_id = device_id

    def allocate(self, size: int) -> Any:
        raise NotImplementedError

    def free(self, ptr: Any):
        raise NotImplementedError

    def copy_to(self, data: Any, src_device: Optional['Device'] = None) -> Any:
        raise NotImplementedError

class CPUDevice(Device):
    """CPU 设备实现。"""
    def __init__(self, device_id: str = "cpu"):
        super().__init__(device_id)

    def allocate(self, size: int) -> Any:
        # 简单模拟
        return bytearray(size)

    def free(self, ptr: Any):
        pass

    def copy_to(self, data: Any, src_device: Optional['Device'] = None) -> Any:
        return data


class Tensor:
    """简易张量抽象，实际数据由后端管理。"""
    def __init__(self, data: Any, device: Device):
        self.data = data
        self.device = device
        self.shape = self._get_shape(data)

    def _get_shape(self, data: Any) -> tuple:
        if hasattr(data, "shape"):
            return tuple(data.shape)
        if isinstance(data, (list, tuple)):
            return (len(data),)
        return ()
