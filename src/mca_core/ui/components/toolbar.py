import tkinter as tk
from tkinter import ttk

class Toolbar:
    def __init__(self, parent, app):
        """
        Initialize the Toolbar (Buttons + Status Hint).
        
        :param parent: The parent frame (usually top_frame).
        :param app: The main application instance (controller).
        """
        self.parent = parent
        self.app = app
        self.status_hint = None
        self._create_widgets()

    def _create_widgets(self):
        # 1. Open Log
        open_btn = ttk.Button(self.parent, text="📂 打开日志", command=self.app.load_file, width=15)
        open_btn.pack(side="left", padx=5)

        # 2. Start Analysis (Primary)
        analyze_btn = ttk.Button(self.parent, text="▶ 开始分析", command=self.app.start_analysis, width=15)
        analyze_btn.pack(side="left", padx=5)

        # 3. Clear text
        clear_btn = ttk.Button(self.parent, text="🗑️ 清除", command=self.app.clear_content, width=10)
        clear_btn.pack(side="left", padx=5)

        # Separator (Vertical)
        ttk.Separator(self.parent, orient="vertical").pack(side="left", fill="y", padx=10, pady=2)
        
        # Info Label
        self.status_hint = ttk.Label(self.parent, text="请加载日志文件...", foreground="#7f8c8d", font=("Segoe UI", 9))
        self.status_hint.pack(side="left", padx=5)

    def update_status(self, text):
        if self.status_hint:
            self.status_hint.config(text=text)
