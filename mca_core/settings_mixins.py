import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as messagebox
import logging
import platform

from mca_core.python_runtime_optimizer import apply_version_specific_optimizations, MODE_DESCRIPTIONS

logger = logging.getLogger("mca_core.app")

class SettingsMixin:
    """Mixin for handling Settings/Optimization UI interactions."""
    
    def _create_opt_tab(self):
        """Builds the Optimization Settings tab UI."""
        # Ensure target frame exists (self.opt_tab expected from main App)
        if not hasattr(self, 'opt_tab'):
            return

        try:
            for w in self.opt_tab.winfo_children():
                w.destroy()
        except Exception:
            pass
        
        main_frame = ttk.Frame(self.opt_tab, padding=20)
        main_frame.pack(fill="both", expand=True)
        
        ttk.Label(main_frame, text="Python 运行时动态优化", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 6))
        ttk.Label(main_frame, text="根据当前 Python 版本调整 GC 策略与线程参数，平衡性能与响应速度。", wraplength=700).pack(anchor="w", pady=(0, 15))

        # 模式变量 (默认标准)
        if not hasattr(self, 'opt_mode_var'):
            self.opt_mode_var = tk.StringVar(value="标准")

        modes_frame = ttk.LabelFrame(main_frame, text="优化模式", padding=15)
        modes_frame.pack(fill="x", anchor="w")

        modes = MODE_DESCRIPTIONS
        
        def _on_mode_change():
            mode = self.opt_mode_var.get()
            try:
                apply_version_specific_optimizations(mode)
                messagebox.showinfo("优化已应用", f"优化模式已切换为：[{mode}]\n相关 GC 与线程参数已即时更新。")
            except Exception as e:
                try:
                    logger.error(f"切换优化模式失败: {e}")
                except: pass

        for mode_name, desc in modes:
            r_frame = ttk.Frame(modes_frame)
            r_frame.pack(fill="x", pady=5)
            # Radiobutton with improved styling
            rb = ttk.Radiobutton(r_frame, text=mode_name, value=mode_name, variable=self.opt_mode_var, command=_on_mode_change)
            rb.pack(side="left")
            ttk.Label(r_frame, text=f" : {desc}", foreground="#555").pack(side="left", padx=5)
        
        # 底部状态信息
        status_frame = ttk.Frame(main_frame, padding=(0, 20))
        status_frame.pack(fill="x", anchor="w")
        ver_info = f"当前环境: Python {platform.python_version()} ({platform.platform()})"
        ttk.Label(status_frame, text=ver_info, foreground="gray").pack(anchor="w")
