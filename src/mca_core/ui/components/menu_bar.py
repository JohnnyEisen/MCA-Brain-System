import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys

class MenuBar:
    def __init__(self, root, app):
        """
        Initialize the MenuBar.
        
        :param root: The root Tkinter window.
        :param app: The main application instance (controller) containing command methods.
        """
        self.root = root
        self.app = app
        self.menubar = tk.Menu(root)
        self._create_menus()
        root.config(menu=self.menubar)

    def _create_menus(self):
        self._create_file_menu()
        self._create_tools_menu()
        self._create_view_menu()
        self._create_help_menu()

    def _create_file_menu(self):
        file_menu = tk.Menu(self.menubar, tearoff=0)
        file_menu.add_command(label="打开日志文件...", command=self.app.load_file)
        file_menu.add_command(label="导入 Mods 列表...", command=self.app.import_mods)
        file_menu.add_command(label="清除", command=self.app.clear_content)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self.root.quit)
        self.menubar.add_cascade(label="文件", menu=file_menu)

    def _create_tools_menu(self):
        tools_menu = tk.Menu(self.menubar, tearoff=0)
        tools_menu.add_command(label="导出依赖关系图谱", command=self.app.export_dependencies)
        tools_menu.add_command(label="导出分析报告 (HTML/TXT)", command=self.app.export_analysis_report)
        tools_menu.add_command(label="查看分析历史", command=self.app.view_history)
        tools_menu.add_separator()
        tools_menu.add_command(label="启动分析引擎", command=self.app._start_ai_init_if_needed)
        tools_menu.add_separator()
        
        # Log Controls
        tools_menu.add_command(label="开启/停止日志实时跟踪 (Tail)", command=self.app._toggle_tail)
        
        tools_menu.add_separator()
        # Advanced Tools
        adv_menu = tk.Menu(tools_menu, tearoff=0)
        adv_menu.add_command(label="启动场景生成器 (CLI)", command=self.app._launch_adversarial_gen)
        adv_menu.add_command(label="GPU 环境配置向导", command=self.app._launch_gpu_setup)
        tools_menu.add_cascade(label="高级诊断工具箱 (Advanced Tools)", menu=adv_menu)
        
        self.menubar.add_cascade(label="工具", menu=tools_menu)

    def _create_view_menu(self):
        view_menu = tk.Menu(self.menubar, tearoff=0)
        # Assuming _apply_styles is public enough or we keep accessing it via app
        view_menu.add_command(label="重置窗口布局", command=self.app._apply_styles) 
        
        # Slider submenu
        sens_menu = tk.Menu(view_menu, tearoff=0)
        # We need to access sens_var and scroll_sensitivity from app
        # If sens_var doesn't exist on app yet, we might need to initialize it there or here.
        # In original code, it checks `if hasattr(self, 'sens_var')`.
        # Ideally, app should initialize its state before UI.
        
        current_sens = getattr(self.app, 'scroll_sensitivity', 3)
        if not hasattr(self.app, 'sens_var'):
             self.app.sens_var = tk.IntVar(value=current_sens)

        for val in [1, 3, 5, 10, 20]:
            sens_menu.add_radiobutton(
                label=f"速度 {val}x", 
                value=val, 
                variable=self.app.sens_var, 
                command=lambda v=val: self.app._set_sensitivity(v)
            )
        view_menu.add_cascade(label="滚动灵敏度", menu=sens_menu)
        
        self.menubar.add_cascade(label="视图", menu=view_menu)

    def _create_help_menu(self):
        help_menu = tk.Menu(self.menubar, tearoff=0)
        help_menu.add_command(label="在线解决方案", command=self.app.setup_solution_browser)
        help_menu.add_command(label="关于", command=self.app.open_help)
        self.menubar.add_cascade(label="帮助", menu=help_menu)
