import logging
from typing import Dict, Any, Optional
import platform

logger = logging.getLogger(__name__)

class SystemService:
    """负责收集系统信息和硬件状态，与 UI 解耦。"""

    def __init__(self):
        self._cached_info: Optional[Dict[str, Any]] = None

    def get_system_info(self) -> Dict[str, Any]:
        """获取系统信息（带缓存）。"""
        if self._cached_info is not None:
            return self._cached_info
        
        self._cached_info = self._collect_info()
        return self._cached_info

    def _collect_info(self) -> Dict[str, Any]:
        info: Dict[str, Any] = {}
        try:
            info['platform'] = platform.platform()
            info['python'] = platform.python_version()
            
            # CPU & Memory
            try:
                import psutil # type: ignore
                info['cpu_count'] = psutil.cpu_count(logical=False)
                info['memory_total'] = getattr(psutil.virtual_memory(), 'total', None)
            except ImportError:
                logger.debug("psutil not installed")
            except Exception:
                logger.debug("Failed to get psutil info")

            # GPU
            try:
                import GPUtil # type: ignore
                gpus = GPUtil.getGPUs()
                info['gpus'] = [{
                    'name': g.name,
                    'driver': getattr(g, 'driver', None),
                    'memoryTotal': getattr(g, 'memoryTotal', None)
                } for g in gpus]
            except ImportError:
                logger.debug("GPUtil not installed")
            except Exception:
                logger.debug("Failed to get GPU info")

        except Exception:
            logger.exception("Failed to collect system info")
        
        return info
