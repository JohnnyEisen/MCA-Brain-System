"""
MCA Brain System - PyQt6 自动测试 Mixin

提供主窗口自动化测试功能。
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from .main_window_pyqt import SiliconeCapsuleApp


SCENARIOS: dict[str, str] = {
    "normal": "正常日志",
    "oom": "内存溢出",
    "missing_dependency": "缺失前置",
    "gl_error": "OpenGL 错误",
    "mixin_conflict": "Mixin 冲突",
    "version_conflict": "版本冲突",
}


class AutoTestMixin:
    """自动化测试功能 Mixin。"""

    def start_auto_test(self: "SiliconeCapsuleApp") -> None:
        """开始自动化测试。"""
        output_dir = self.auto_test_output_edit.text().strip() or os.path.join(self._get_root_dir(), "tmp", "autotests")
        os.makedirs(output_dir, exist_ok=True)

        selected = self.auto_test_scenarios.selectedItems()
        scenarios = [item.text().split("-")[0].strip() for item in selected]
        if not scenarios:
            scenarios = ["normal"]

        count = int(self.auto_test_count_spin.value())
        cleanup = bool(self.auto_test_cleanup_check.isChecked())
        run_analysis = bool(self.auto_test_run_analysis_check.isChecked())

        self.auto_test_log_edit.clear()
        self.auto_test_progress.setValue(0)
        self.auto_test_progress.setMaximum(max(count, 1))
        self.btn_auto_test_start.setEnabled(False)
        self.btn_auto_test_stop.setEnabled(True)
        self.auto_test_stats_label.setText("统计: 运行中...")
        self.tabs.setCurrentIndex(4)

        from mca_core.workers_pyqt import AutoTestWorker
        worker = AutoTestWorker(
            output_dir, 
            scenarios, 
            count, 
            cleanup,
            engine=self.engine,
            run_analysis=run_analysis
        )
        worker.signals.log.connect(self.auto_test_log_edit.append)
        worker.signals.progress.connect(lambda cur, total: self.auto_test_progress.setValue(cur))
        worker.signals.stats.connect(self.on_auto_test_stats)
        worker.signals.error.connect(self.on_auto_test_error)
        worker.signals.finished.connect(self.on_auto_test_finished)
        self.auto_test_worker = worker
        worker.start()

    def stop_auto_test(self: "SiliconeCapsuleApp") -> None:
        """停止自动化测试。"""
        if self.auto_test_worker:
            self.auto_test_worker.cancel()
            self.auto_test_log_edit.append("用户请求停止自动化测试...")

    def on_auto_test_stats(self: "SiliconeCapsuleApp", gen_time: str, samples: str, cleanup_msg: str) -> None:
        """处理自动化测试统计。"""
        self.auto_test_stats_label.setText(f"统计: 生成耗时 {gen_time}, 样本数 {samples}, {cleanup_msg}")

    def on_auto_test_error(self: "SiliconeCapsuleApp", msg: str) -> None:
        """处理自动化测试错误。"""
        self.auto_test_log_edit.append(f"[错误] {msg}")

    def on_auto_test_finished(self: "SiliconeCapsuleApp") -> None:
        """处理自动化测试完成。"""
        self.btn_auto_test_start.setEnabled(True)
        self.btn_auto_test_stop.setEnabled(False)
        self.auto_test_log_edit.append("自动化测试结束。")
        self.auto_test_worker = None

    def _get_root_dir(self: "SiliconeCapsuleApp") -> str:
        """获取项目根目录。"""
        import os
        script_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.dirname(os.path.dirname(script_dir))
