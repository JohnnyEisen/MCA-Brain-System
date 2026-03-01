"""UI Mixin - UI创建/鼠标事件/窗口管理"""

from __future__ import annotations
import os
import sys
import json
import time
import logging
import threading
from typing import TYPE_CHECKING
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

from config.constants import (
    MOD_DB_FILE, LOADER_DB_FILE, MOD_CONFLICTS_FILE, GPU_ISSUES_FILE,
    BASE_DIR, DEFAULT_SCROLL_SENSITIVITY, ROOT_DIR
)


class UIMixin:
    """Mixin for UI creation and event handling."""
    
    def _init_ui_components(self):
        from mca_core.ui.components.menu_bar import MenuBar
        from mca_core.ui.components.toolbar import Toolbar
        from mca_core.ui.components.brain_monitor import BrainMonitor
        from mca_core.ui.components.main_notebook import MainNotebook
        
        self._tail_btn_var = tk.StringVar(value="开始跟踪")
        self.sens_var = tk.IntVar(value=getattr(self, 'scroll_sensitivity', DEFAULT_SCROLL_SENSITIVITY))
        self.menu_bar = MenuBar(self.root, self)
        self._create_main_panes()
        self.progress = ttk.Progressbar(self.scrollable_frame, mode="indeterminate")
        
        top_frame = ttk.Frame(self.scrollable_frame, padding=12)
        top_frame.pack(fill="x", padx=10, pady=(5, 0))
        self.toolbar = Toolbar(top_frame, self)
        self.brain_monitor = BrainMonitor(top_frame, self.root)
        self.status_var.trace_add("write", lambda *args: self.toolbar.update_status(self.status_var.get()))
        
        bottom_frame = ttk.Frame(self.scrollable_frame)
        bottom_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.main_notebook = MainNotebook(bottom_frame, self)
        
        self.auto_test_tab = ttk.Frame(self.main_notebook.notebook)
        self.main_notebook.notebook.add(self.auto_test_tab, text="自动化测试")
        self._create_auto_test_tab()
        
        self.opt_tab = ttk.Frame(self.main_notebook.notebook)
        self.main_notebook.notebook.add(self.opt_tab, text="运行时优化")
        self._create_opt_tab()

    @property
    def result_text(self):
        return self.main_notebook.result_text
        
    @property
    def hw_text(self):
        return self.main_notebook.hw_text
        
    @property
    def graph_frame(self):
        return self.main_notebook.graph_frame
        
    @property
    def browser(self):
        return self.main_notebook.browser
        
    @property
    def layout_var(self):
        return self.main_notebook.layout_var
        
    @property
    def filter_isolated_var(self):
        return self.main_notebook.filter_isolated_var
        
    @property
    def web_search_var(self):
        return self.main_notebook.web_search_var

    @property
    def ai_status_var(self):
        return self.brain_monitor.status_var

    def _create_main_panes(self):
        self.scrollable_frame = ttk.Frame(self.root)
        self.scrollable_frame.pack(fill="both", expand=True)
        try:
            self.root.bind_all("<MouseWheel>", self._on_mousewheel)
            self.root.bind_all("<Button-4>", self._on_mousewheel)
            self.root.bind_all("<Button-5>", self._on_mousewheel)
        except Exception as e:
            logger.exception("绑定鼠标滚轮失败: %s", e)

    def _on_mousewheel(self, event):
        try:
            widget = event.widget
            target_scrollable = None
            curr = widget
            while curr and curr != self.root:
                if hasattr(curr, "yview") and (isinstance(curr, (tk.Text, tk.Canvas, tk.Listbox)) or "scrolledtext" in str(type(curr))):
                    target_scrollable = curr
                    break
                if hasattr(curr, "yview") and "Treeview" in str(type(curr)):
                    target_scrollable = curr
                    break
                curr = getattr(curr, "master", None)
            if target_scrollable:
                delta = getattr(event, "delta", 0)
                num = getattr(event, "num", 0)
                step = 0
                if delta:
                    step = int(-1 * (delta / 120))
                elif num == 4:
                    step = -1
                elif num == 5:
                    step = 1
                if step != 0:
                    try:
                        target_scrollable.yview_scroll(step * getattr(self, 'scroll_sensitivity', 1), "units")
                    except Exception: 
                        pass
                return "break"
            return 
        except Exception:
            pass

    def _create_log_area(self):
        log_frame = ttk.LabelFrame(self.scrollable_frame, text="崩溃日志", padding=6)
        log_frame.pack(fill="both", expand=False, padx=10, pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, height=18, wrap="none", font=("Consolas", 10))
        self.log_text.pack(fill="both", expand=True)
        try:
            self.log_text.bind("<Enter>", lambda e: self.log_text.focus_set())
        except Exception:
            pass
        self.log_text.tag_config("highlight", background="#f39c12", foreground="black")
        self.log_text.tag_config("error", background="#e74c3c", foreground="white")
        self.log_text.config(state="disabled")

    def _ensure_db_files(self):
        for p in (MOD_DB_FILE, LOADER_DB_FILE, MOD_CONFLICTS_FILE, GPU_ISSUES_FILE):
            if not os.path.exists(p):
                try:
                    if p == MOD_CONFLICTS_FILE:
                        default = {"blacklist": [{"render": ["iris", "sodium", "optifine"], "world": ["twilightforest"], "note": "兼容性问题"}], "whitelist": []}
                        with open(p, "w", encoding="utf-8") as f:
                            json.dump(default, f, ensure_ascii=False, indent=2)
                        continue
                    if p == GPU_ISSUES_FILE:
                        gpu_default = {"rules": [{"vendor": "nvidia", "match": ["nvidia"], "advice": "更新驱动"}]}
                        with open(p, "w", encoding="utf-8") as f:
                            json.dump(gpu_default, f, ensure_ascii=False, indent=2)
                        continue
                    with open(p, "w", encoding="utf-8") as f:
                        json.dump({}, f, ensure_ascii=False, indent=2)
                except Exception as e:
                    logger.error(f"无法创建默认数据库文件 {p}: {e}")
        try:
            self._load_gpu_issues()
        except Exception:
            self.gpu_issues = {}

    def _load_gpu_issues(self):
        try:
            if os.path.exists(GPU_ISSUES_FILE):
                with open(GPU_ISSUES_FILE, "r", encoding="utf-8") as f:
                    self.gpu_issues = json.load(f)
            else:
                self.gpu_issues = {}
        except Exception as e:
            logger.exception("无法加载 GPU issues 文件: %s", e)
            self.gpu_issues = {}

    def _load_conflict_db(self):
        try:
            with open(MOD_CONFLICTS_FILE, "r", encoding="utf-8") as f:
                self.conflict_db = json.load(f)
        except Exception:
            self.conflict_db = {"blacklist": [], "whitelist": []}
        for section in ("blacklist", "whitelist"):
            items = self.conflict_db.get(section) or []
            for it in items:
                it["render"] = [r.lower() for r in it.get("render", [])]
                it["world"] = [w.lower() for w in it.get("world", [])]

    def _center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"+{x}+{y}")

    def _apply_styles(self):
        """应用统一的 UI 样式配置。"""
        try:
            from mca_core.ui.styles import apply_styles
            
            # 获取主题配置
            theme = "light"
            if hasattr(self, 'app_config') and hasattr(self.app_config, 'theme'):
                theme = self.app_config.theme
            
            # 应用统一样式
            self._style_config = apply_styles(self.root, theme)
            
        except Exception as e:
            # 回退到 sv_ttk
            try:
                import sv_ttk
                theme = getattr(getattr(self, "app_config", None), "theme", "light")
                sv_ttk.set_theme(theme)
            except Exception as e2:
                logger.warning(f"无法应用 UI 主题: {e}, {e2}")

    def _set_sensitivity(self, val):
        self.scroll_sensitivity = val
        if hasattr(self, 'sens_var'):
            self.sens_var.set(val)

    def _launch_adversarial_gen(self):
        try:
            script_path = os.path.join(ROOT_DIR, "tools", "generate_mc_log.py")
            if os.name == 'nt':
                import subprocess
                subprocess.Popen(
                    ['cmd', '/c', 'start', 'cmd', '/k', f'"{sys.executable}" "{script_path}" --help'],
                    detached=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                messagebox.showinfo("Tip", "Please run in terminal: python tools/generate_mc_log.py")
        except Exception as e:
            messagebox.showerror("Launch failed", str(e))

    def _launch_gpu_setup(self):
        try:
            script_path = os.path.join(ROOT_DIR, "tools", "gpu_setup.py")
            if os.name == 'nt':
                os.system(f'start cmd /k "{sys.executable} {script_path}"')
            else:
                messagebox.showinfo("提示", "请在终端运行: python tools/gpu_setup.py")
        except Exception as e:
            messagebox.showerror("启动失败", str(e))

    def open_help(self):
        messagebox.showinfo("关于", "Minecraft Crash Analyzer (v1.0 - Brain System)\n\nPowered by BrainCore Architecture.")

    def on_window_close(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        def _cleanup_task():
            try:
                if self.brain:
                    logger.info("正在关闭 Brain System 资源...")
                    for dlc in self.brain.dlcs.values():
                        if hasattr(dlc, "shutdown"):
                            try:
                                dlc_thread = threading.Thread(target=dlc.shutdown)
                                dlc_thread.start()
                                dlc_thread.join(timeout=1.0)
                            except Exception:
                                pass
                    if self.brain.thread_pool:
                        self.brain.thread_pool.shutdown(wait=False)
                    if self.brain.process_pool:
                        self.brain.process_pool.shutdown(wait=False)
            except Exception as e:
                logger.error(f"清理资源失败: {e}")
            finally:
                time.sleep(0.2)
                os._exit(0)
        t = threading.Thread(target=_cleanup_task, daemon=True)
        t.start()

    def _on_tab_changed(self, event):
        pass

    # ---------- Hardware Analysis Methods ----------
    
    def _detect_gl_errors(self):
        """Invoke GL detector standalone for hardware tab refresh."""
        try:
            from mca_core.detectors import AnalysisContext
            if hasattr(self, '_gl_errors_detector') and self._gl_errors_detector:
                ctx = AnalysisContext(self, self.crash_log or "")
                self._gl_errors_detector.detect(self.crash_log or "", ctx)
        except Exception:
            pass

    def _refresh_hardware_analysis(self):
        """Refresh hardware analysis and display in hardware tab."""
        try:
            self._detect_gl_errors()
        except Exception:
            pass
        try:
            self.hw_text.config(state="normal")
            self.hw_text.delete("1.0", tk.END)
            if self.gpu_info:
                for k, v in self.gpu_info.items():
                    self.hw_text.insert(tk.END, f"{k}: {v}\n")
            if self.hardware_issues:
                self.hw_text.insert(tk.END, "\n硬件相关建议:\n")
                for l in self.hardware_issues:
                    self.hw_text.insert(tk.END, "- " + l + "\n")
            if getattr(self, 'gl_snippets', None):
                self.hw_text.insert(tk.END, "\nGL/Shader 相关片段:\n")
                for s in self.gl_snippets:
                    self.hw_text.insert(tk.END, s + "\n---\n")
            self.hw_text.config(state="disabled")
        except Exception:
            pass

    def _copy_gl_snippets(self):
        """Copy GL snippets to clipboard."""
        try:
            txt = "\n---\n".join(self.gl_snippets or [])
            self.root.clipboard_clear()
            self.root.clipboard_append(txt)
            messagebox.showinfo("复制成功", "GL 相关片段已复制到剪贴板。")
        except Exception:
            messagebox.showerror("复制失败", "无法复制到剪贴板。")

    def setup_solution_browser(self, init_only=False):
        self.main_notebook.setup_solution_browser(init_only)
        if not init_only:
            try:
                self.main_notebook.notebook.select(self.main_notebook.web_tab)
            except Exception: 
                pass
