"""
MCA Brain System - PyQt6 分析 Mixin

提供主窗口分析功能。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from PyQt6.QtWidgets import QMessageBox

if TYPE_CHECKING:
    from .main_window_pyqt import SiliconeCapsuleApp


class AnalysisMixin:
    """分析功能 Mixin。"""

    def on_analyze_clicked(self: "SiliconeCapsuleApp") -> None:
        """处理分析按钮点击。"""
        log_content = self.log_text.toPlainText()
        if not log_content.strip():
            QMessageBox.warning(self, "提示", "请先加载或输入崩溃日志内容。")
            return

        self.result_text.clear()
        self.mods_text.clear()
        self.hardware_text_edit.clear()
        self.progress_bar.setValue(0)
        self.status_label.setText("状态: 分析中...")

        self.analyze_btn.setEnabled(False)
        self._cancel_event.clear()

        from mca_core.workers_pyqt import AnalysisWorker
        worker = AnalysisWorker(
            self.engine,
            self.brain,
            log_content
        )
        worker.signals.progress.connect(self.on_analysis_progress)
        worker.signals.append_log.connect(self.on_analysis_append)
        worker.signals.finished.connect(self.on_analysis_finished)
        worker.signals.error.connect(self.on_analysis_error)
        self.analysis_worker = worker
        worker.start()

    def on_analysis_progress(self: "SiliconeCapsuleApp", val: int, msg: str) -> None:
        """处理分析进度更新。"""
        self.progress_bar.setValue(val)
        self.status_label.setText(f"状态: {msg}")

    def on_analysis_append(self: "SiliconeCapsuleApp", msg: str) -> None:
        """追加分析日志。"""
        self.result_text.append(msg)

    def on_analysis_finished(
        self: "SiliconeCapsuleApp",
        results: list[str],
        mods_info: dict[str, Any],
        hw_info: dict[str, Any],
        graph_data: Optional[dict[str, Any]]
    ) -> None:
        """处理分析完成。"""
        self.analyze_btn.setEnabled(True)
        self.progress_bar.setValue(100)
        self.status_label.setText("状态: 分析完成")

        if results:
            for r in results:
                self.result_text.append(r)

        if mods_info:
            self._display_mods_info(mods_info)

        if hw_info:
            self._display_hw_info(hw_info)

        if graph_data:
            self.draw_graphs(graph_data)

    def on_analysis_error(self: "SiliconeCapsuleApp", err_msg: str) -> None:
        """处理分析错误。"""
        self.analyze_btn.setEnabled(True)
        self.status_label.setText("状态: 分析出错")
        QMessageBox.critical(self, "分析错误", err_msg)

    def finish_analysis(self: "SiliconeCapsuleApp") -> None:
        """完成分析。"""
        self.analyze_btn.setEnabled(True)
        self.status_label.setText("状态: 就绪")

    def _display_mods_info(self: "SiliconeCapsuleApp", mods_info: dict[str, Any]) -> None:
        """显示模组信息。"""
        mods = mods_info.get("mods", {})
        if mods:
            self.mods_text.append(f"检测到 {len(mods)} 个模组:\n")
            for mod_id, versions in sorted(mods.items()):
                self.mods_text.append(f"  • {mod_id}: {', '.join(sorted(versions))}")

    def _display_hw_info(self: "SiliconeCapsuleApp", hw_info: dict[str, Any]) -> None:
        """显示硬件信息。"""
        gpu = hw_info.get("gpu", "未知")
        driver = hw_info.get("driver", "未知")
        java = hw_info.get("java", "未知")
        memory = hw_info.get("memory", "未知")

        self.hardware_text_edit.append("硬件分析报告:\n")
        self.hardware_text_edit.append(f"GPU: {gpu}")
        self.hardware_text_edit.append(f"驱动: {driver}")
        self.hardware_text_edit.append(f"Java: {java}")
        self.hardware_text_edit.append(f"内存: {memory}")

        suggestions = hw_info.get("suggestions", [])
        if suggestions:
            self.hardware_text_edit.append("\n建议:")
            for s in suggestions:
                self.hardware_text_edit.append(f"  • {s}")
