"""
文件操作 Mixin 模块

提供文件加载、Tail 跟踪和导出功能。

模块说明:
    本模块实现了文件操作相关的功能，通过 Mixin 模式为主应用提供服务。
    
    主要组件:
        - FileOpsMixinHost: 文件操作宿主接口协议
        - FileOpsMixin: 文件操作 Mixin 类

功能列表:
    - 文件加载（单文件/多文件）
    - 日志文本更新和高亮
    - 内容清除
    - Tail 实时跟踪
    - 依赖关系导出
    - 分析报告导出
    - 历史记录查看
    - Mods 文件夹导入
"""

from __future__ import annotations

import csv
import logging
import os
import threading
import time
from collections import defaultdict, Counter
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

import tkinter as tk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk

if TYPE_CHECKING:
    from mca_core.services.log_service import LogService

from mca_core.threading_utils import submit_task
from config.constants import BASE_DIR, HIGHLIGHT_SIZE_LIMIT, HISTORY_FILE

logger = logging.getLogger(__name__)


# ============================================================
# 宿主协议定义 - Host Protocol Definition
# ============================================================

@runtime_checkable
class FileOpsMixinHost(Protocol):
    """
    文件操作宿主接口协议。
    
    定义 FileOpsMixin 需要宿主类提供的方法和属性。
    """
    
    root: tk.Tk
    status_var: tk.StringVar
    crash_log: str
    file_path: str
    log_service: "LogService"
    log_text: tk.Text
    result_text: tk.Text
    analysis_results: list[str]
    mods: dict[str, set]
    mod_names: dict[str, str]
    dependency_pairs: set[tuple[str, str]]
    loader_type: str | None
    cause_counts: Any
    main_notebook: Any
    gpu_info: dict
    hardware_issues: list
    gl_snippets: list
    hw_text: tk.Text | None
    progress: ttk.Progressbar
    _tail_running: bool
    _tail_btn_var: tk.StringVar
    _tail_lock: threading.Lock
    highlight_size_limit: int
    
    def update_log_text(self) -> None: ...
    def detect_and_load_file(self, path: str) -> None: ...
    def detect_and_load_multiple_files(self, paths: tuple[str, ...]) -> None: ...
    def _on_file_loaded(self) -> None: ...
    def _on_load_error(self, e: Exception) -> None: ...
    def _invalidate_log_cache(self) -> None: ...
    def _clean_modid(self, raw: str) -> str: ...
    def _tail_worker(self) -> None: ...
    def _append_log_line(self, line: str) -> None: ...


# ============================================================
# 文件操作 Mixin - File Operations Mixin
# ============================================================

class FileOpsMixin:
    """
    文件操作 Mixin。
    
    提供文件加载、Tail 跟踪和导出功能。
    
    Attributes:
        root: Tkinter 根窗口
        status_var: 状态变量
        crash_log: 崩溃日志文本
        file_path: 文件路径
        log_service: 日志服务
        log_text: 日志文本控件
        result_text: 结果文本控件
        analysis_results: 分析结果列表
        mods: 模组字典
        mod_names: 模组名称字典
        dependency_pairs: 依赖关系对
        loader_type: 加载器类型
        cause_counts: 崩溃原因计数器
        main_notebook: 主笔记本控件
        gpu_info: GPU 信息
        hardware_issues: 硬件问题列表
        gl_snippets: GL 片段列表
        hw_text: 硬件信息文本控件
        progress: 进度条
        _tail_running: Tail 是否运行
        _tail_btn_var: Tail 按钮变量
        _tail_lock: Tail 锁
        highlight_size_limit: 高亮大小限制
    
    方法:
        - load_file: 加载文件
        - detect_and_load_file: 检测并加载单个文件
        - detect_and_load_multiple_files: 检测并加载多个文件
        - update_log_text: 更新日志文本
        - clear_content: 清除内容
        - _toggle_tail: 切换 Tail 状态
        - export_dependencies: 导出依赖关系
        - export_analysis_report: 导出分析报告
        - view_history: 查看历史记录
        - import_mods: 导入模组
    """
    
    root: tk.Tk
    status_var: tk.StringVar
    crash_log: str
    file_path: str
    log_service: "LogService"
    log_text: tk.Text
    result_text: tk.Text
    analysis_results: list[str]
    mods: dict[str, set]
    mod_names: dict[str, str]
    dependency_pairs: set[tuple[str, str]]
    loader_type: str | None
    cause_counts: Any
    main_notebook: Any
    gpu_info: dict
    hardware_issues: list
    gl_snippets: list
    hw_text: tk.Text | None
    progress: ttk.Progressbar
    _tail_running: bool
    _tail_btn_var: tk.StringVar
    _tail_lock: threading.Lock
    highlight_size_limit: int

    def load_file(self: FileOpsMixinHost) -> None:
        """
        打开文件选择对话框并加载文件。
        
        支持单文件和多文件选择。
        """
        paths = filedialog.askopenfilenames(
            filetypes=[("日志文件", "*.log *.txt"), ("所有文件", "*.*")]
        )
        if not paths:
            return
        if len(paths) == 1:
            self.detect_and_load_file(paths[0])
        else:
            self.detect_and_load_multiple_files(paths)

    def detect_and_load_multiple_files(
        self: FileOpsMixinHost,
        paths: tuple[str, ...]
    ) -> None:
        """
        检测并加载多个文件。
        
        Args:
            paths: 文件路径元组
        """
        def on_success() -> None:
            self.root.after(0, self._on_file_loaded)
        
        def on_error(e: Exception) -> None:
            self.root.after(0, lambda: self._on_load_error(e))
        
        self.status_var.set(f"正在加载 {len(paths)} 个文件...")
        self.log_service.load_from_multiple_files_async(list(paths), on_success, on_error)

    def detect_and_load_file(self: FileOpsMixinHost, file_path: str) -> None:
        """
        检测并加载单个文件。
        
        Args:
            file_path: 文件路径
        """
        def on_success() -> None:
            self.root.after(0, self._on_file_loaded)
        
        def on_error(e: Exception) -> None:
            self.root.after(0, lambda: self._on_load_error(e))
        
        def on_progress(p: float, msg: str) -> None:
            pass
        
        self.status_var.set("加载文件中...")
        self.log_service.load_from_file_async(file_path, on_success, on_error, on_progress)

    def _on_file_loaded(self: FileOpsMixinHost) -> None:
        """文件加载成功回调。"""
        self.update_log_text()
        self.status_var.set("日志已加载")
    
    def _on_load_error(self: FileOpsMixinHost, e: Exception) -> None:
        """
        文件加载错误回调。
        
        Args:
            e: 异常对象
        """
        messagebox.showerror("加载失败", f"错误: {e}")
        self.status_var.set("加载失败")

    def update_log_text(self: FileOpsMixinHost) -> None:
        """
        更新日志文本控件。
        
        包括关键词高亮和滚动位置保持。
        """
        try:
            yview = self.log_text.yview()
        except Exception:
            yview = None
        
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(tk.END, self.crash_log)
        
        if len(self.crash_log) <= getattr(self, "highlight_size_limit", HIGHLIGHT_SIZE_LIMIT):
            keywords = [
                "exception", "error", "crash", "outofmemory",
                "out of memory", "FAILED", "FATAL"
            ]
            for kw in keywords:
                start_idx = "1.0"
                while True:
                    start_idx = self.log_text.search(
                        kw, start_idx, stopindex=tk.END, nocase=True
                    )
                    if not start_idx:
                        break
                    end_idx = f"{start_idx}+{len(kw)}c"
                    try:
                        self.log_text.tag_add("highlight", start_idx, end_idx)
                    except Exception:
                        pass
                    start_idx = end_idx
        
        try:
            if yview:
                self.log_text.yview_moveto(yview[0])
        except Exception:
            pass
        finally:
            self.log_text.config(state="disabled")

    def clear_content(self: FileOpsMixinHost) -> None:
        """清除所有内容和状态。"""
        self.crash_log = ""
        self.file_path = ""
        self.analysis_results = []
        self._invalidate_log_cache()
        self.mods = defaultdict(set)
        self.mod_names = {}
        self.dependency_pairs = set()
        self.loader_type = None
        self.cause_counts = Counter()
        
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.config(state="disabled")
        
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.config(state="disabled")
        
        self.status_var.set("已清除")
        
        for w in self.main_notebook.canvas_container.winfo_children():
            w.destroy()
        self.main_notebook.graph_placeholder = ttk.Label(
            self.main_notebook.canvas_container,
            text="分析后显示依赖关系图",
            foreground="#666666"
        )
        self.main_notebook.graph_placeholder.pack(expand=True)
        
        self.gpu_info = {}
        self.hardware_issues = []
        self.gl_snippets = []
        
        try:
            self.hw_text.config(state="normal")
            self.hw_text.delete("1.0", tk.END)
            self.hw_text.config(state="disabled")
        except Exception:
            pass
        
        for w in self.main_notebook.cause_canvas_container.winfo_children():
            w.destroy()
        self.main_notebook.cause_placeholder = ttk.Label(
            self.main_notebook.cause_canvas_container,
            text="分析后显示崩溃原因占比",
            foreground="#666666"
        )
        self.main_notebook.cause_placeholder.pack(expand=True)

    def _toggle_tail(self: FileOpsMixinHost) -> None:
        """
        切换 Tail 实时跟踪状态。
        
        线程安全地管理 Tail 状态。
        """
        with getattr(self, '_tail_lock', threading.Lock()):
            if self._tail_running:
                self._tail_running = False
                self._tail_btn_var.set("开始跟踪")
                self.status_var.set("日志跟踪已停止")
            else:
                if not self.file_path or not os.path.exists(self.file_path):
                    messagebox.showinfo("提示", "请先加载一个有效的本地日志文件。")
                    return
                self._tail_running = True
                self._tail_btn_var.set("停止跟踪")
                self.status_var.set("正在跟踪日志变化...")
                threading.Thread(target=self._tail_worker, daemon=True).start()

    def _tail_worker(self: FileOpsMixinHost) -> None:
        """
        Tail 工作线程。
        
        持续监视文件变化并追加新内容。
        """
        _tail_lock = getattr(self, '_tail_lock', threading.Lock())
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, 2)
                while True:
                    with _tail_lock:
                        if not self._tail_running:
                            break
                    line = f.readline()
                    if line:
                        self.root.after(0, lambda l=line: self._append_log_line(l))
                    else:
                        time.sleep(0.5)
        except Exception as e:
            logging.getLogger(__name__).error(f"Tail error: {e}")
            with _tail_lock:
                self._tail_running = False
            self.root.after(0, lambda: self._tail_btn_var.set("开始跟踪(出错)"))

    def _append_log_line(self: FileOpsMixinHost, line: str) -> None:
        """
        追加日志行到文本控件。
        
        Args:
            line: 日志行
        """
        self.log_text.config(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def export_dependencies(self: FileOpsMixinHost) -> None:
        """导出依赖关系到 CSV 文件。"""
        if not self.dependency_pairs:
            messagebox.showinfo("提示", "没有依赖数据可导出。")
            return
        
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV 文件", "*.csv")],
            initialfile=f"mod_dependencies_{int(time.time())}.csv"
        )
        if not path:
            return
        
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["Source Mod", "Requires Target", "Status"])
                for src, tgt in self.dependency_pairs:
                    status = "Missing" if tgt not in self.mods else "Present"
                    writer.writerow([src, tgt, status])
            messagebox.showinfo("导出成功", f"依赖表已保存至: {path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def export_analysis_report(self: FileOpsMixinHost) -> None:
        """导出分析报告到文本文件。"""
        if not self.analysis_results:
            messagebox.showinfo("提示", "暂无分析结果。")
            return
        
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt")]
        )
        if not path:
            return
        
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"MCA Analysis Report - {datetime.now().isoformat()}\n")
                f.write("=" * 50 + "\n\n")
                for line in self.analysis_results:
                    f.write(line + "\n")
            messagebox.showinfo("导出成功", f"报告已保存: {path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def view_history(self: FileOpsMixinHost) -> None:
        """查看分析历史记录。"""
        try:
            if not os.path.exists(HISTORY_FILE):
                messagebox.showinfo("历史", "暂无历史记录。")
                return
            
            win = tk.Toplevel(self.root)
            win.title("分析历史")
            win.geometry("800x400")
            
            tree = ttk.Treeview(win, columns=("time", "summary", "path"), show="headings")
            tree.heading("time", text="时间")
            tree.column("time", width=150)
            tree.heading("summary", text="摘要")
            tree.column("summary", width=400)
            tree.heading("path", text="文件路径")
            tree.column("path", width=200)
            
            scrollbar = ttk.Scrollbar(win, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scrollbar.set)
            tree.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")
            
            with open(HISTORY_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.reader(f)
                rows = list(reader)
                for row in reversed(rows):
                    if len(row) >= 3:
                        tree.insert("", "end", values=row[:3])
            
            def _on_dbl_click(event: Any) -> None:
                item = tree.selection()
                if not item:
                    return
                vals = tree.item(item[0], "values")
                if len(vals) >= 3 and os.path.exists(vals[2]):
                    self.detect_and_load_file(vals[2])
                    win.destroy()
            
            tree.bind("<Double-1>", _on_dbl_click)
        except Exception as e:
            messagebox.showerror("错误", f"无法读取历史记录: {e}")

    def import_mods(self: FileOpsMixinHost) -> None:
        """从 Mods 文件夹导入模组信息。"""
        from mca_core.regex_cache import RegexCache
        
        folder = filedialog.askdirectory(title="选择 .minecraft/mods 文件夹")
        if not folder:
            return
        
        self.progress.pack(fill="x", padx=10, pady=(4, 6))
        self.progress.config(mode="indeterminate")
        self.progress.start(10)
        self.status_var.set("正在扫描 Mods 文件夹...")
        
        def _scan() -> None:
            try:
                mod_files: list[str] = []
                for root_dir, _, files in os.walk(folder):
                    for f in files:
                        if f.endswith(".jar"):
                            mod_files.append(f)
                
                self.mods = defaultdict(set)
                for f in mod_files:
                    m = RegexCache.search(r"([a-zA-Z0-9_\-]+)-(\d[\w\.\-]+)\.jar", f)
                    if m:
                        mid = self._clean_modid(m.group(1))
                        if mid:
                            self.mods[mid].add(m.group(2))
                
                self.root.after(
                    0, 
                    lambda: self.status_var.set(f"已导入 {len(self.mods)} 个模组")
                )
                self.root.after(
                    0,
                    lambda: messagebox.showinfo(
                        "导入完成",
                        f"在文件夹中发现 {len(self.mods)} 个模组。"
                    )
                )
            except Exception as e:
                self.root.after(
                    0,
                    lambda: messagebox.showerror("导入失败", str(e))
                )
            finally:
                self.root.after(0, self.progress.stop)
                self.root.after(0, lambda: self.progress.pack_forget())
        
        submit_task(_scan)
