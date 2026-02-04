from __future__ import annotations

import os
import csv
from datetime import datetime
from typing import Any

from tkinter import filedialog, messagebox

from mca_core.exporters import ReportExporter, AnalysisReport


class AnalysisEventMixin:
    def _on_analysis_start_event(self, event: Any):
        try:
            self.status_var.set("分析中...")
        except Exception:
            pass

    def _on_analysis_complete_event(self, event: Any):
        try:
            self.status_var.set("分析完成")
        except Exception:
            pass

    def _on_analysis_error_event(self, event: Any):
        try:
            self.status_var.set("分析失败")
        except Exception:
            pass

    def _on_analysis_progress_event(self, event: Any):
        try:
            msg = event.payload.get("message")
            if msg:
                self.status_var.set(msg)
        except Exception:
            pass

    def _on_detector_complete_event(self, event: Any):
        try:
            name = event.payload.get("detector")
            if name:
                self.status_var.set(f"检测完成: {name}")
        except Exception:
            pass

    def _on_progress_report(self, value: float, message: str = ""):
        def _apply():
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

    def cancel_analysis(self):
        try:
            self._cancel_event.set()
        except Exception:
            pass

    def _is_cancelled(self) -> bool:
        try:
            return self._cancel_event.is_set()
        except Exception:
            return False

    def export_dependencies(self):
        if not self.mods:
            messagebox.showinfo("提示", "没有依赖数据可导出，请先执行分析。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV 文件", "*.csv")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["mod_id", "versions", "display_name"])
                for modid, vers in sorted(self.mods.items()):
                    writer.writerow([modid, ";".join(sorted(vers)), self.mod_names.get(modid, "")])
            messagebox.showinfo("完成", f"已导出到: {path}")
        except Exception as e:
            messagebox.showerror("导出失败", f"导出失败: {e}")

    def export_analysis_report(self):
        if not self.analysis_results:
            messagebox.showinfo("提示", "没有分析结果可导出，请先执行分析。")
            return
        try:
            path = filedialog.asksaveasfilename(
                defaultextension=".html",
                filetypes=[("HTML", "*.html"), ("Markdown", "*.md"), ("JSON", "*.json"), ("PDF", "*.pdf"), ("所有文件", "*.*")],
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
