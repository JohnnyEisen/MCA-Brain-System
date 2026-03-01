"""Hardware Accelerator DLC: 真实管理 GPU/CPU 资源，优先使用 CuPy。"""
from __future__ import annotations

import logging
import multiprocessing
import threading
import warnings
from typing import Any, Dict, List, Optional
import asyncio

from brain_system import BrainCore, BrainDLC, BrainDLCType, DLCManifest
from brain_system.utils import optional_import, require_optional, Device, CPUDevice

# 导入可选依赖
psutil = optional_import("psutil")

class CUDADevice(Device):
    """NVIDIA CUDA 设备封装 (基于 CuPy)。"""
    def __init__(self, device_id: str, index: int, cp_mod: Any):
        super().__init__(device_id)
        self.index = index
        self.cp = cp_mod
        self.handle = self.cp.cuda.Device(index)
        self.pool = self.cp.cuda.MemoryPool()
        self.cp.cuda.set_allocator(self.pool.malloc)

    def allocate(self, size: int) -> Any:
        # CuPy 自动管理内存，这里仅做演示性接口
        # 实际开发中通常直接创建 cupy.ndarray
        with self.handle:
            return self.cp.zeros(size, dtype=self.cp.uint8)

    def free(self, ptr: Any):
        # Python GC + MemoryPool 会自动回收
        del ptr

    def copy_to(self, data: Any, src_device: Optional[Device] = None) -> Any:
        """从 Host 或其他 Device 复制数据到本 GPU。"""
        with self.handle:
            return self.cp.asarray(data)

    def sync(self):
        self.handle.synchronize()


class HardwareAcceleratorDLC(BrainDLC):
    """DLC: 硬件加速与资源管理。"""

    def get_manifest(self) -> DLCManifest:
        return DLCManifest(
            name="Hardware Accelerator",
            version="1.1.0",
            author="Brain AI Systems",
            description="支持GPU/CPU硬件加速，自动检测 CuPy/Numpy 环境",
            dlc_type=BrainDLCType.PROCESSOR,
            dependencies=["Brain Core"],  # 基础能力，不依赖其他 DLC
            priority=10
        )

    def _initialize(self):
        self.available_devices: Dict[str, Dict[str, Any]] = self._detect_hardware()
        self.device_objects: Dict[str, Device] = {}
        
        # 预加载 NumPy
        self.np = require_optional(optional_import("numpy"), "numpy", "请安装 numpy")

        self._init_devices_real()
        self._start_monitor()
        logging.info(f"硬件加速加载完毕，可用设备: {list(self.available_devices.keys())}")

    def shutdown(self):
        if hasattr(self, "_stop_event"):
            self._stop_event.set()
        # 清理引用，辅助 GC
        self.device_objects.clear()

    def provide_computational_units(self) -> Dict[str, Any]:
        return {
            "get_device": self.get_device,
            "list_devices": self.list_devices,
            "tensor_op": self.execute_tensor_op,
            "numpy_module": self.get_numpy_compat,
        }

    # --- 核心功能 ---

    def get_device(self, device_id: str) -> Optional[Device]:
        return self.device_objects.get(device_id)

    def get_device_str(self) -> str:
        """
        获取首选计算设备的字符串标识 (用于 Torch/TensorFlow)。
        优先顺序: CUDA (FP16) > MPS (Mac) > CPU (Default)。
        """
        # 1. 检查是否有已识别的 GPU
        for did, info in self.available_devices.items():
            if info.get("type") == "cuda":
                return "cuda"
        # 2. 默认回退
        return "cpu"

    def get_float_type(self):
        """
        获取推荐的浮点精度。
        如果使用 CUDA，则推荐 FP16 (Half Precision) 以提升算力吞吐量。
        如果使用 CPU，则推荐 FP32（某些旧 CPU 对 FP16 支持不佳反而变慢）。
        """
        if self.get_device_str() == "cuda":
            # [Optimization] Return float16 for mixed precision
            return "float16"
        return "float32"

    def list_devices(self) -> Dict[str, Dict[str, Any]]:
        return self.available_devices

    def get_numpy_compat(self, device_id: str = "cpu"):
        """获取兼容的数值库（numpy 或 cupy）。"""
        dev = self.get_device(device_id)
        if isinstance(dev, CUDADevice):
            return dev.cp
        return self.np

    def execute_tensor_op(self, op: str, *args, device_id="cpu", **kwargs):
        """在指定设备上执行简单算子 (matmul, dot, sum 等)。"""
        xp = self.get_numpy_compat(device_id)
        if hasattr(xp, op):
            func = getattr(xp, op)
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logging.error(f"算子执行失败 {op} on {device_id}: {e}")
                raise
        else:
            raise ValueError(f"设备 {device_id} ({xp.__name__}) 不支持操作 {op}")

    # --- 内部实现 ---

    def _detect_hardware(self) -> Dict[str, Dict[str, Any]]:
        devices = {
            "cpu": {
                "type": "cpu",
                "cores": multiprocessing.cpu_count(),
                "memory_gb": self._get_sys_memory_gb()
            }
        }
        
        # 检测 NVIDIA GPU (通过 import cupy)
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", ".*CUDA path.*")
                import cupy
                cnt = cupy.cuda.runtime.getDeviceCount()
                for i in range(cnt):
                    props = cupy.cuda.runtime.getDeviceProperties(i)
                    name = props.get("name", b"Unknown GPU").decode("utf-8", "ignore")
                    mem = props.get("totalGlobalMem", 0)
                    devices[f"gpu_{i}"] = {
                        "type": "cuda",
                        "index": i,
                        "name": name,
                        "memory_mb": mem // (1024*1024)
                    }
        except ImportError:
            pass  # 没装 cupy
        except Exception as e:
            logging.warning(f"GPU 检测异常: {e}")

        return devices

    def _init_devices_real(self):
        # 初始化 CPU
        self.device_objects["cpu"] = CPUDevice("cpu")

        # 初始化 GPU
        if any(k.startswith("gpu_") for k in self.available_devices):
            try:
                import cupy
                for did, info in self.available_devices.items():
                    if info["type"] == "cuda":
                        self.device_objects[did] = CUDADevice(did, info["index"], cupy)
            except ImportError:
                logging.warning("此环境无法加载 CuPy，禁用 GPU 加速。")

    def _get_sys_memory_gb(self) -> float:
        if psutil:
            return psutil.virtual_memory().total / (1024**3)
        return 0.0

    def _start_monitor(self):
        self._stop_event = threading.Event()
        # 简单起见，不在此处做重型轮询（Monitoring 模块已负责）
        pass
