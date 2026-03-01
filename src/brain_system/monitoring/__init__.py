"""monitoring: 性能监控模块（资源/指标）。"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Any, Optional

from ..utils import optional_import

psutil = optional_import("psutil")

class PerformanceMonitor:
    """性能监控器，负责收集系统与Brain指标。"""

    def __init__(self, interval: float = 5.0):
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._metrics: Dict[str, Any] = {
            "cpu_percent": 0.0,
            "memory_percent": 0.0,
            "brain_tasks": 0,
        }

    def start_monitoring(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logging.info("性能监控已启动")

    def stop_monitoring(self) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        logging.info("性能监控已停止")

    def get_metrics(self) -> Dict[str, Any]:
        return self._metrics.copy()

    def update_brain_metrics(self, tasks_completed: int):
        self._metrics["brain_tasks"] = tasks_completed

    def _run_loop(self):
        while not self._stop_event.is_set():
            try:
                self._collect_system_metrics()
            except Exception as e:
                logging.warning(f"监控采集失败: {e}")
            time.sleep(self.interval)

    def _collect_system_metrics(self):
        if psutil:
            self._metrics["cpu_percent"] = psutil.cpu_percent(interval=None)
            self._metrics["memory_percent"] = psutil.virtual_memory().percent
