"""
UI 事件处理 Mixin 模块

提供分析事件处理、进度报告和导出功能。

类说明:
    - AnalysisEventMixin: 分析事件处理 Mixin，处理分析生命周期事件
"""

from __future__ import annotations

import csv
import os
import threading
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from tkinter import filedialog, messagebox

if TYPE_CHECKING:
    from tkinter import Tk
    from tkinter.ttk import Progressbar

from mca_core.exporters import AnalysisReport, ReportExporter


class AnalysisEventMixin:
    """
    分析事件处理 Mixin。
    
    提供分析生命周期事件处理方法，包括开始、完成、错误和进度事件。
    该 Mixin 假设宿主类具有以下属性:
        - status_var: tk.StringVar 状态变量
        - root: Tk 根窗口
        - progress: Progressbar 进度条控件
        - _cancel_event: threading.Event 取消事件
        - mods: dict 模组字典
        - mod_names: dict 模组名称字典
        - analysis_results: list 分析结果列表
    
    方法:
        - _on_analysis_start_event: 分析开始事件处理
        - _on_analysis_complete_event: 分析完成事件处理
        - _on_analysis_error_event: 分析错误事件处理
        - _on_analysis_progress_event: 分析进度事件处理
        - _on_detector_complete_event: 检测器完成事件处理
        - _on_progress_report: 进度报告回调
        - cancel_analysis: 取消分析
        - _is_cancelled: 检查是否已取消
        - export_dependencies: 导出依赖关系
        - export_analysis_report: 导出分析报告
    """
    
    status_var: Any
    root: Any
    progress: Any
    _cancel_event: threading.Event
    mods: dict[str, set]
    mod_names: dict[str, str]
    analysis_results: list[str]

    def _on_analysis_start_event(self, event: Any) -> None:
        """
        处理分析开始事件。
        
        Args:
            event: 事件对象
        """
        try:
            self.status_var.set("分析中...")
        except Exception:
            pass

    def _on_analysis_complete_event(self, event: Any) -> None:
        """
        处理分析完成事件。
        
        Args:
            event: 事件对象
        """
        try:
            self.status_var.set("分析完成")
        except Exception:
            pass

    def _on_analysis_error_event(self, event: Any) -> None:
        """
        处理分析错误事件。
        
        Args:
            event: 事件对象
        """
        try:
            self.status_var.set("分析失败")
        except Exception:
            pass

    def _on_analysis_progress_event(self, event: Any) -> None:
        """
        处理分析进度事件。
        
        Args:
            event: 事件对象，应包含 payload 字典
        """
        try:
            msg = event.payload.get("message")
            if msg:
                self.status_var.set(msg)
        except Exception:
            pass

    def _on_detector_complete_event(self, event: Any) -> None:
        """
        处理检测器完成事件。
        
        Args:
            event: 事件对象，应包含 payload 字典
        """
        try:
            name = event.payload.get("detector")
            if name:
                self.status_var.set(f"检测完成: {name}")
        except Exception:
            pass

    def _on_progress_report(self, value: float, message: str = "") -> None:
        """
        报告分析进度。
        
        Args:
            value: 进度值 (0.0 - 1.0)
            message: 进度消息
        """
        def _apply() -> None:
            try:
                if message:
                    self.status_var.set(message)
                if value and 0.0 <= value <= 1.0:
                    try:
                        self.progress.config(mode="determinate", maximum=100)
                        self.progress["value"] = int(value * 100)
                    except Exception:
                        pass
            except Exception:
                pass
        
        try:
            self.root.after(0, _apply)
        except Exception:
            pass

    def cancel_analysis(self) -> None:
        """取消当前分析操作。"""
        try:
            self._cancel_event.set()
        except Exception:
            pass

    def _is_cancelled(self) -> bool:
        """
        检查分析是否已被取消。
        
        Returns:
            如果已取消返回 True，否则返回 False
        """
        try:
            return self._cancel_event.is_set()
        except Exception:
            return False

    def export_dependencies(self) -> None:
        """导出模组依赖关系到 CSV 文件。"""
        if not self.mods:
            messagebox.showinfo("提示", "没有依赖数据可导出，请先执行分析。")
            return
            
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")]
        )
        if not path:
            return
            
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["mod_id", "versions", "display_name"])
                for modid, vers in sorted(self.mods.items()):
                    writer.writerow([
                        modid,
                        ";".join(sorted(vers)),
                        self.mod_names.get(modid, "")
                    ])
            messagebox.showinfo("完成", f"已导出到: {path}")
        except Exception as e:
            messagebox.showerror("导出失败", f"导出失败: {e}")

    def export_analysis_report(self) -> None:
        """导出分析报告到多种格式。"""
        if not self.analysis_results:
            messagebox.showinfo("提示", "没有分析结果可导出，请先执行分析。")
            return
            
        try:
            path = filedialog.asksaveasfilename(
                defaultextension=".html",
                filetypes=[
                    ("HTML", "*.html"),
                    ("Markdown", "*.md"),
                    ("JSON", "*.json"),
                    ("PDF", "*.pdf"),
                    ("所有文件", "*.*")
                ],
            )
            if not path:
                return
                
            ext = os.path.splitext(path)[1].lower().lstrip(".")
            format_type = ext if ext in {"html", "md", "markdown", "json", "pdf"} else "html"
            if format_type == "md":
                format_type = "markdown"
                
            title = f"崩溃分析报告 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            content = "\n".join(self.analysis_results)
            report = AnalysisReport(title=title, content=content)
            ReportExporter().export(report, format_type, path)
            messagebox.showinfo("完成", f"已导出到: {path}")
        except Exception as e:
            messagebox.showerror("导出失败", f"导出失败: {e}")
