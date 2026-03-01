"""文件操作 Mixin - 文件加载/Tail跟踪/导出"""

from __future__ import annotations
import os
import time
import csv
import threading
from datetime import datetime
from typing import TYPE_CHECKING
import tkinter as tk
from tkinter import filedialog, messagebox

if TYPE_CHECKING:
    pass

from mca_core.threading_utils import submit_task
from config.constants import BASE_DIR, HIGHLIGHT_SIZE_LIMIT, HISTORY_FILE


class FileOpsMixin:
    """Mixin for file operations."""
    
    def load_file(self):
        paths = filedialog.askopenfilenames(filetypes=[("日志文件", "*.log *.txt"), ("所有文件", "*.*")])
        if not paths:
            return
        if len(paths) == 1:
            self.detect_and_load_file(paths[0])
        else:
            self.detect_and_load_multiple_files(paths)

    def detect_and_load_multiple_files(self, paths):
        def on_success():
            self.root.after(0, self._on_file_loaded)
        def on_error(e):
            self.root.after(0, lambda: self._on_load_error(e))
        self.status_var.set(f"正在加载 {len(paths)} 个文件...")
        self.log_service.load_from_multiple_files_async(paths, on_success, on_error)

    def detect_and_load_file(self, file_path):
        def on_success():
            self.root.after(0, self._on_file_loaded)
        def on_error(e):
            self.root.after(0, lambda: self._on_load_error(e))
        def on_progress(p, msg):
            pass
        self.status_var.set("加载文件中...")
        self.log_service.load_from_file_async(file_path, on_success, on_error, on_progress)

    def _on_file_loaded(self):
        self.update_log_text()
        self.status_var.set("日志已加载")
    
    def _on_load_error(self, e):
        messagebox.showerror("加载失败", f"错误: {e}")
        self.status_var.set("加载失败")

    def update_log_text(self):
        try:
            yview = self.log_text.yview()
        except Exception:
            yview = None
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", tk.END)
        self.log_text.insert(tk.END, self.crash_log)
        if len(self.crash_log) <= getattr(self, "highlight_size_limit", HIGHLIGHT_SIZE_LIMIT):
            keywords = ["exception", "error", "crash", "outofmemory", "out of memory", "FAILED", "FATAL"]
            for kw in keywords:
                start_idx = "1.0"
                while True:
                    start_idx = self.log_text.search(kw, start_idx, stopindex=tk.END, nocase=True)
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

    def clear_content(self):
        from collections import defaultdict, Counter
        import tkinter.ttk as ttk
        
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
        self.main_notebook.graph_placeholder = ttk.Label(self.main_notebook.canvas_container, text="分析后显示依赖关系图", foreground="#666666")
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
        self.main_notebook.cause_placeholder = ttk.Label(self.main_notebook.cause_canvas_container, text="分析后显示崩溃原因占比", foreground="#666666")
        self.main_notebook.cause_placeholder.pack(expand=True)

    def _toggle_tail(self):
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

    def _tail_worker(self):
        import logging
        try:
            with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
                f.seek(0, 2)
                while self._tail_running:
                    line = f.readline()
                    if line:
                        self.root.after(0, lambda l=line: self._append_log_line(l))
                    else:
                        time.sleep(0.5)
        except Exception as e:
            logging.getLogger(__name__).error(f"Tail error: {e}")
            self._tail_running = False
            self.root.after(0, lambda: self._tail_btn_var.set("开始跟踪(出错)"))

    def _append_log_line(self, line):
        self.log_text.config(state="normal")
        self.log_text.insert("end", line)
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def export_dependencies(self):
        if not self.dependency_pairs:
            messagebox.showinfo("提示", "没有依赖数据可导出。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV 文件", "*.csv")], initialfile=f"mod_dependencies_{int(time.time())}.csv")
        if not path: return
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

    def export_analysis_report(self):
        if not self.analysis_results:
            messagebox.showinfo("提示", "暂无分析结果。")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text File", "*.txt")])
        if not path: return
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"MCA Analysis Report - {datetime.now().isoformat()}\n")
                f.write("="*50 + "\n\n")
                for line in self.analysis_results:
                    f.write(line + "\n")
            messagebox.showinfo("导出成功", f"报告已保存: {path}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def view_history(self):
        import tkinter.ttk as ttk
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
            def _on_dbl_click(event):
                item = tree.selection()
                if not item: return
                vals = tree.item(item[0], "values")
                if len(vals) >= 3 and os.path.exists(vals[2]):
                    self.detect_and_load_file(vals[2])
                    win.destroy()
            tree.bind("<Double-1>", _on_dbl_click)
        except Exception as e:
            messagebox.showerror("错误", f"无法读取历史记录: {e}")

    def import_mods(self):
        from collections import defaultdict
        from mca_core.regex_cache import RegexCache
        folder = filedialog.askdirectory(title="选择 .minecraft/mods 文件夹")
        if not folder:
            return
        self.progress.pack(fill="x", padx=10, pady=(4, 6))
        self.progress.config(mode="indeterminate")
        self.progress.start(10)
        self.status_var.set("正在扫描 Mods 文件夹...")
        def _scan():
            try:
                mod_files = []
                for root, _, files in os.walk(folder):
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
                self.root.after(0, lambda: self.status_var.set(f"已导入 {len(self.mods)} 个模组"))
                self.root.after(0, lambda: messagebox.showinfo("导入完成", f"在文件夹中发现 {len(self.mods)} 个模组。"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("导入失败", str(e)))
            finally:
                self.root.after(0, self.progress.stop)
                self.root.after(0, lambda: self.progress.pack_forget())
        submit_task(_scan)
