"""
日志视图组件。

负责崩溃日志的显示、高亮和滚动管理。
"""

import tkinter as tk
from tkinter import scrolledtext, ttk
from typing import Optional, List, Callable


class LogView:
    """
    日志视图组件。
    
    负责显示崩溃日志内容，支持关键词高亮和滚动位置保持。
    """
    
    # 默认高亮关键词
    DEFAULT_HIGHLIGHT_KEYWORDS = [
        "exception", "error", "crash", "outofmemory", 
        "out of memory", "FAILED", "FATAL"
    ]
    
    def __init__(
        self,
        parent: tk.Widget,
        highlight_limit: int = 300_000,
        on_scroll_callback: Optional[Callable] = None,
    ):
        """
        初始化日志视图。
        
        Args:
            parent: 父组件
            highlight_limit: 启用高亮的最大日志大小
            on_scroll_callback: 滚动回调（用于同步滚动）
        """
        self.parent = parent
        self._highlight_limit = highlight_limit
        self._on_scroll = on_scroll_callback
        
        # 创建文本控件
        self.text = scrolledtext.ScrolledText(
            parent,
            state="disabled",
            height=20,
            font=("Consolas", 10),
            wrap=tk.WORD,
        )
        self.text.pack(fill="both", expand=True, padx=4, pady=4)
        
        # 配置高亮标签
        self.text.tag_config("highlight", background="#ffff99")
        self.text.tag_config("error", foreground="#e74c3c", font=("Consolas", 10, "bold"))
        self.text.tag_config("warning", foreground="#f39c12")
        
        # 绑定事件
        self._setup_bindings()
    
    def _setup_bindings(self):
        """设置事件绑定。"""
        try:
            # 鼠标滚轮绑定（用于自定义滚动处理）
            self.text.bind("<MouseWheel>", self._on_mousewheel)
            self.text.bind("<Button-4>", self._on_mousewheel)
            self.text.bind("<Button-5>", self._on_mousewheel)
            
            # 焦点管理
            self.text.bind("<Enter>", lambda e: self.text.focus_set())
        except Exception:
            pass
    
    def _on_mousewheel(self, event):
        """鼠标滚轮事件处理。"""
        if self._on_scroll:
            self._on_scroll(event)
    
    def set_content(self, content: str, highlight: bool = True):
        """
        设置日志内容。
        
        Args:
            content: 日志文本
            highlight: 是否启用关键词高亮
        """
        # 保存当前滚动位置
        try:
            yview = self.text.yview()
        except Exception:
            yview = None
        
        # 更新内容
        self.text.config(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.insert(tk.END, content)
        
        # 应用高亮
        if highlight and len(content) <= self._highlight_limit:
            self._apply_highlights(content)
        
        # 恢复滚动位置
        try:
            if yview:
                self.text.yview_moveto(yview[0])
        except Exception:
            pass
        finally:
            self.text.config(state="disabled")
    
    def _apply_highlights(self, content: str):
        """应用关键词高亮。"""
        for kw in self.DEFAULT_HIGHLIGHT_KEYWORDS:
            start_idx = "1.0"
            while True:
                start_idx = self.text.search(
                    kw, start_idx, stopindex=tk.END, nocase=True
                )
                if not start_idx:
                    break
                end_idx = f"{start_idx}+{len(kw)}c"
                try:
                    self.text.tag_add("highlight", start_idx, end_idx)
                except Exception:
                    pass
                start_idx = end_idx
    
    def clear(self):
        """清除日志内容。"""
        self.text.config(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.config(state="disabled")
    
    def append(self, text: str, scroll_to_end: bool = True):
        """
        追加文本到末尾。
        
        Args:
            text: 要追加的文本
            scroll_to_end: 是否滚动到末尾
        """
        self.text.config(state="normal")
        self.text.insert(tk.END, text)
        if scroll_to_end:
            self.text.see(tk.END)
        self.text.config(state="disabled")
    
    def get_content(self) -> str:
        """获取当前内容。"""
        return self.text.get("1.0", tk.END)
    
    def scroll_to(self, position: float):
        """
        滚动到指定位置。
        
        Args:
            position: 0.0-1.0 之间的位置
        """
        try:
            self.text.yview_moveto(position)
        except Exception:
            pass
    
    def scroll_to_top(self):
        """滚动到顶部。"""
        self.scroll_to(0.0)
    
    def scroll_to_bottom(self):
        """滚动到底部。"""
        self.scroll_to(1.0)
    
    def set_highlight_limit(self, limit: int):
        """
        设置高亮大小限制。
        
        Args:
            limit: 最大字节数
        """
        self._highlight_limit = limit
    
    def enable(self):
        """启用控件。"""
        self.text.config(state="normal")
    
    def disable(self):
        """禁用控件（只读）。"""
        self.text.config(state="disabled")
    
    def focus(self):
        """获取焦点。"""
        try:
            self.text.focus_set()
        except Exception:
            pass


class ResultView:
    """
    结果视图组件。
    
    负责分析结果的显示，支持不同类型的格式化。
    """
    
    def __init__(self, parent: tk.Widget):
        """
        初始化结果视图。
        
        Args:
            parent: 父组件
        """
        self.parent = parent
        
        # 创建文本控件
        self.text = scrolledtext.ScrolledText(
            parent,
            state="disabled",
            height=12,
            font=("Segoe UI", 10),
        )
        self.text.pack(fill="both", expand=True, padx=8, pady=8)
        
        # 配置标签样式
        self.text.tag_config(
            "ai_header", 
            foreground="#2980b9", 
            font=("Segoe UI", 11, "bold")
        )
        self.text.tag_config(
            "ai_content", 
            foreground="#2c3e50", 
            background="#eaf2f8"
        )
        self.text.tag_config(
            "error", 
            foreground="#e74c3c",
            font=("Segoe UI", 10, "bold")
        )
        self.text.tag_config(
            "warning", 
            foreground="#f39c12"
        )
        
        try:
            self.text.bind("<Enter>", lambda e: self.text.focus_set())
        except Exception:
            pass
    
    def display(self, results: List[str]):
        """
        显示分析结果。
        
        Args:
            results: 结果文本列表
        """
        self.text.config(state="normal")
        self.text.delete("1.0", tk.END)
        
        if not results:
            self.text.config(state="disabled")
            return
        
        for line in results:
            tag = self._get_tag_for_line(line)
            self.text.insert(tk.END, line + "\n", tag)
        
        self.text.config(state="disabled")
    
    def _get_tag_for_line(self, line: str) -> Optional[str]:
        """根据行内容确定显示标签。"""
        if "智能" in line and "建议" in line:
            return "ai_header"
        if "AI 深度理解" in line or "关键特征匹配" in line:
            return "ai_content"
        if "错误" in line or "失败" in line:
            return "error"
        if "警告" in line or "注意" in line:
            return "warning"
        return None
    
    def clear(self):
        """清除内容。"""
        self.text.config(state="normal")
        self.text.delete("1.0", tk.END)
        self.text.config(state="disabled")
    
    def append(self, text: str, tag: Optional[str] = None):
        """追加文本。"""
        self.text.config(state="normal")
        if tag:
            self.text.insert(tk.END, text + "\n", tag)
        else:
            self.text.insert(tk.END, text + "\n")
        self.text.config(state="disabled")
