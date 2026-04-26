"""
系统服务模块

负责收集系统信息和硬件状态，与 UI 解耦。

类说明:
    - SystemService: 系统信息服务，收集 CPU、内存、GPU 等硬件信息
"""

from __future__ import annotations

import logging
import platform
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class SystemService:
    """
    系统信息服务。
    
    负责收集系统信息和硬件状态，与 UI 解耦。
    使用缓存策略避免重复收集信息。
    
    Attributes:
        _cached_info: 缓存的系统信息
    
    方法:
        - get_system_info: 获取系统信息（带缓存）
        - _collect_info: 收集系统信息
    """

    def __init__(self) -> None:
        """初始化系统服务。"""
        self._cached_info: Optional[Dict[str, Any]] = None

    def get_system_info(self) -> Dict[str, Any]:
        """
        获取系统信息（带缓存）。
        
        Returns:
            包含系统信息的字典
        """
        if self._cached_info is not None:
            return self._cached_info

        self._cached_info = self._collect_info()
        return self._cached_info

    def _collect_info(self) -> Dict[str, Any]:
        """
        收集系统信息。
        
        Returns:
            包含系统信息的字典
        """
        info: Dict[str, Any] = {}

        self._collect_platform_info(info)
        self._collect_cpu_memory_info(info)
        self._collect_gpu_info(info)

        return info

    def _collect_platform_info(self, info: Dict[str, Any]) -> None:
        """
        收集平台信息。
        
        Args:
            info: 信息字典，会被直接修改
        """
        try:
            info['platform'] = platform.platform()
            info['python'] = platform.python_version()
        except Exception:
            logger.debug("Failed to get platform info")

    def _collect_cpu_memory_info(self, info: Dict[str, Any]) -> None:
        """
        收集 CPU 和内存信息。
        
        Args:
            info: 信息字典，会被直接修改
        """
        try:
            import psutil

            info['cpu_count'] = psutil.cpu_count(logical=False)
            info['memory_total'] = getattr(
                psutil.virtual_memory(),
                'total',
                None
            )
        except ImportError:
            logger.debug("psutil not installed")
        except Exception:
            logger.debug("Failed to get psutil info")

    def _collect_gpu_info(self, info: Dict[str, Any]) -> None:
        """
        收集 GPU 信息。
        
        Args:
            info: 信息字典，会被直接修改
        """
        try:
            import GPUtil

            gpus: List[Any] = GPUtil.getGPUs()
            info['gpus'] = [
                {
                    'name': g.name,
                    'driver': getattr(g, 'driver', None),
                    'memoryTotal': getattr(g, 'memoryTotal', None)
                }
                for g in gpus
            ]
        except ImportError:
            logger.debug("GPUtil not installed")
        except Exception:
            logger.debug("Failed to get GPU info")

    def clear_cache(self) -> None:
        """清除缓存的系统信息。"""
        self._cached_info = None
