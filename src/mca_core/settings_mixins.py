"""
设置 Mixin 模块

提供 Python 运行时优化设置的 UI 和逻辑。

类说明:
    - SettingsMixin: 设置界面 Mixin，处理优化模式切换
"""

from __future__ import annotations

import logging
import platform
from typing import TYPE_CHECKING, Any

import tkinter as tk
from tkinter import ttk
import tkinter.messagebox as messagebox

if TYPE_CHECKING:
    from tkinter import Tk

from mca_core.python_runtime_optimizer import MODE_DESCRIPTIONS, apply_version_specific_optimizations

logger = logging.getLogger("mca_core.app")


class SettingsMixin:
    """
    设置界面 Mixin。
    
    提供 Python 运行时动态优化的 UI 和逻辑处理。
    该 Mixin 假设宿主类具有以下属性:
        - opt_tab: 设置标签页容器
        - opt_mode_var: tk.StringVar 优化模式变量 (可选，会自动创建)
    
    Attributes:
        opt_mode_var: 优化模式选择变量
    
    方法:
        - _create_opt_tab: 创建优化设置标签页
    """

    opt_mode_var: tk.StringVar
    opt_tab: Any

    def _create_opt_tab(self) -> None:
        """
        构建优化设置标签页 UI。
        
        创建包含优化模式选择和系统信息显示的界面。
        """
        if not hasattr(self, 'opt_tab'):
            return

        try:
            for w in self.opt_tab.winfo_children():
                w.destroy()
        except Exception:
            pass

        main_frame = ttk.Frame(self.opt_tab, padding=20)
        main_frame.pack(fill="both", expand=True)

        self._create_opt_header(main_frame)
        self._create_opt_modes(main_frame)
        self._create_opt_status(main_frame)

    def _create_opt_header(self, parent: ttk.Frame) -> None:
        """
        创建设置页标题区域。
        
        Args:
            parent: 父容器
        """
        ttk.Label(
            parent,
            text="Python 运行时动态优化",
            font=("Segoe UI", 12, "bold")
        ).pack(anchor="w", pady=(0, 6))

        ttk.Label(
            parent,
            text="根据当前 Python 版本调整 GC 策略与线程参数，平衡性能与响应速度。",
            wraplength=700
        ).pack(anchor="w", pady=(0, 15))

    def _create_opt_modes(self, parent: ttk.Frame) -> None:
        """
        创建优化模式选择区域。
        
        Args:
            parent: 父容器
        """
        if not hasattr(self, 'opt_mode_var'):
            self.opt_mode_var = tk.StringVar(value="标准")

        modes_frame = ttk.LabelFrame(parent, text="优化模式", padding=15)
        modes_frame.pack(fill="x", anchor="w")

        for mode_name, desc in MODE_DESCRIPTIONS:
            self._create_mode_option(modes_frame, mode_name, desc)

    def _create_mode_option(self, parent: Any, mode_name: str, desc: str) -> None:
        """
        创建单个优化模式选项。
        
        Args:
            parent: 父容器
            mode_name: 模式名称
            desc: 模式描述
        """
        r_frame = ttk.Frame(parent)
        r_frame.pack(fill="x", pady=5)

        ttk.Radiobutton(
            r_frame,
            text=mode_name,
            value=mode_name,
            variable=self.opt_mode_var,
            command=self._on_mode_change
        ).pack(side="left")

        ttk.Label(
            r_frame,
            text=f" : {desc}",
            foreground="#555"
        ).pack(side="left", padx=5)

    def _on_mode_change(self) -> None:
        """处理优化模式变更。"""
        mode = self.opt_mode_var.get()
        try:
            apply_version_specific_optimizations(mode)
            messagebox.showinfo(
                "优化已应用",
                f"优化模式已切换为：[{mode}]\n相关 GC 与线程参数已即时更新。"
            )
        except Exception as e:
            logger.error(f"切换优化模式失败: {e}")

    def _create_opt_status(self, parent: ttk.Frame) -> None:
        """
        创建状态信息区域。
        
        Args:
            parent: 父容器
        """
        status_frame = ttk.Frame(parent, padding=(0, 20))
        status_frame.pack(fill="x", anchor="w")

        ver_info = f"当前环境: Python {platform.python_version()} ({platform.platform()})"
        ttk.Label(status_frame, text=ver_info, foreground="gray").pack(anchor="w")
