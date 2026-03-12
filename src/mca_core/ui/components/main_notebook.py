import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import webbrowser
import logging
from collections import Counter
from urllib.parse import quote_plus
from mca_core.security import InputSanitizer

logger = logging.getLogger("mca_core")

# Optional dependencies
try:
    from tkinterweb import HtmlFrame
    HAS_HTMLFRAME = True
except ImportError:
    HAS_HTMLFRAME = False

try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    import matplotlib.pyplot as plt
    # Config fonts
    plt.rcParams['font.sans-serif'] = ['Microsoft YaHei', 'SimHei', 'Arial Unicode MS', 'sans-serif']
    plt.rcParams['axes.unicode_minus'] = False
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

class MainNotebook:
    def __init__(self, parent, app):
        """
        Initialize the Main Notebook (Tabs).
        
        :param parent: Parent widget.
        :param app: Main application instance (Controller).
        """
        self.parent = parent
        self.app = app
        
        self.notebook = ttk.Notebook(parent)
        self.notebook.pack(fill="both", expand=True)

        # Public Widgets (for App access)
        self.result_text = None
        self.graph_frame = None
        self.hw_text = None
        self.browser = None
        
        # Vars
        self.layout_var = tk.StringVar(value="Hierarchy (树形)")
        self.filter_isolated_var = tk.BooleanVar(value=True)
        self.web_search_var = tk.StringVar(value="minecraft crash solutions")

        self._create_tabs()

    def _create_tabs(self):
        # 1. Analysis Results
        self.analysis_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.analysis_tab, text="分析结果")
        self._create_analysis_tab()

        # 2. Cause Breakdown
        self.cause_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.cause_tab, text="原因占比")
        self._create_cause_tab()

        # 3. Dependency Graph
        self.graph_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.graph_tab, text="MOD依赖关系图")
        self._create_graph_tab()

        # 4. Online Solution
        self.web_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.web_tab, text="在线解决方案")
        self.setup_solution_browser(init_only=True)

        # 5. Hardware Diagnostics
        self.hw_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.hw_tab, text="硬件诊断")
        self._create_hw_tab()

    def _create_analysis_tab(self):
        self.result_text = scrolledtext.ScrolledText(self.analysis_tab, state="disabled", height=12, font=("Segoe UI", 10))
        self.result_text.pack(fill="both", expand=True, padx=8, pady=8)
        
        self.result_text.tag_config("ai_header", foreground="#2980b9", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_config("ai_content", foreground="#2c3e50", background="#eaf2f8")
        
        try:
            self.result_text.bind("<Enter>", lambda e: self.result_text.focus_set())
        except Exception:
            pass

    def _create_cause_tab(self):
        frame = ttk.Frame(self.cause_tab, padding=8)
        frame.pack(fill="both", expand=True)
        self.cause_canvas_container = ttk.Frame(frame)
        self.cause_canvas_container.pack(fill="both", expand=True)
        self.cause_placeholder = ttk.Label(self.cause_canvas_container, text="分析后显示崩溃原因占比", foreground="#666666")
        self.cause_placeholder.pack(expand=True)

    def _create_graph_tab(self):
        self.graph_frame = ttk.Frame(self.graph_tab, padding=8)
        self.graph_frame.pack(fill="both", expand=True)
        
        ctrl = ttk.Frame(self.graph_frame)
        ctrl.pack(fill="x")
        
        # Layout selector
        ttk.Label(ctrl, text="布局算法:").pack(side="left", padx=(0, 4))
        self.layout_combo = ttk.Combobox(ctrl, textvariable=self.layout_var, state="readonly", width=16)
        self.layout_combo['values'] = (
            "Hierarchy (树形)", "Spring (力导向)", "Circular (圆形)", 
            "Shell (同心圆)", "Spectral (谱布局)", "Random (随机)"
        )
        self.layout_combo.pack(side="left", padx=4)
        self.layout_combo.bind("<<ComboboxSelected>>", lambda e: self.app.update_dependency_graph())

        # Filter switch
        ttk.Checkbutton(ctrl, text="隐藏无依赖MOD", variable=self.filter_isolated_var, command=self.app.update_dependency_graph).pack(side="left", padx=10)

        # Buttons
        ttk.Button(ctrl, text="保存图表", command=self.app.save_dependency_graph).pack(side="right", padx=6)
        ttk.Button(ctrl, text="导出依赖(CSV)", command=self.app.export_dependencies).pack(side="right", padx=6)
        ttk.Button(ctrl, text="查看历史", command=self.app.view_history).pack(side="right", padx=6)

        self.canvas_container = ttk.Frame(self.graph_frame)
        self.canvas_container.pack(fill="both", expand=True, pady=6)

        self.graph_placeholder = ttk.Label(self.canvas_container, text="分析后显示依赖关系图", foreground="#666666")
        self.graph_placeholder.pack(expand=True)

    def _create_hw_tab(self):
        top = ttk.Frame(self.hw_tab, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="硬件诊断（基于日志的启发式检测）").pack(side="left")
        ttk.Button(top, text="刷新检测", command=self.app._refresh_hardware_analysis).pack(side="right")

        body = ttk.Frame(self.hw_tab, padding=8)
        body.pack(fill="both", expand=True)

        self.hw_text = scrolledtext.ScrolledText(body, height=12)
        self.hw_text.pack(fill="both", expand=True)

        ctrl = ttk.Frame(self.hw_tab)
        ctrl.pack(fill="x", pady=6)
        ttk.Button(ctrl, text="复制 GL 片段", command=self.app._copy_gl_snippets).pack(side="right", padx=6)

    def setup_solution_browser(self, init_only=False):
        # Clear old
        for w in self.web_tab.winfo_children():
            w.destroy()

        # Search Bar
        ctrl = ttk.Frame(self.web_tab, padding=6)
        ctrl.pack(fill="x", padx=6, pady=(6, 0))
        
        ttk.Entry(ctrl, textvariable=self.web_search_var).pack(side="left", fill="x", expand=True, padx=(0,6))
        
        def _do_search():
            query = self.web_search_var.get().strip()
            if not query: return
            url = f"https://www.bing.com/search?q={quote_plus(query)}"
            
            if HAS_HTMLFRAME and self.browser:
                try:
                    # Try different methods for HtmlFrame compatibility
                    if hasattr(self.browser, 'load_website'): self.browser.load_website(url)
                    elif hasattr(self.browser, 'load_url'): self.browser.load_url(url)
                    elif hasattr(self.browser, 'set_content'): 
                        self.browser.set_content(f'<iframe src="{url}" style="border:0;width:100%;height:100%"></iframe>')
                    return
                except Exception:
                    logger.warning("HtmlFrame load failed, fallback to external")
            
            safe_url = InputSanitizer.sanitize_url(url)
            if safe_url: webbrowser.open(safe_url)

        ttk.Button(ctrl, text="搜索", command=_do_search, width=10).pack(side="left", padx=2)
        
        def _open_external():
            q = self.web_search_var.get().strip()
            url = f"https://www.bing.com/search?q={quote_plus(q)}"
            safe = InputSanitizer.sanitize_url(url)
            if safe: webbrowser.open(safe)

        ttk.Button(ctrl, text="在外部浏览器打开", command=_open_external, width=18).pack(side="right", padx=2)

        # Quick Links
        links_frame = ttk.Frame(self.web_tab, padding=6)
        links_frame.pack(fill="x", padx=6, pady=(4,0))
        ttk.Label(links_frame, text="常用搜索/资源:").pack(side="left")
        
        def _open_link(q):
            url = f"https://www.bing.com/search?q={quote_plus(q)}"
            safe = InputSanitizer.sanitize_url(url)
            if safe: webbrowser.open(safe)

        for txt, q in [("Crash 系统日志 模式","minecraft crash log common causes"), ("GeckoLib 错误","geckolib missing mod crash"), ("OpenGL / GLFW 错误","opengl glfw crash minecraft")]:
            ttk.Button(links_frame, text=txt, command=lambda qq=q: _open_link(qq), width=18).pack(side="left", padx=4)

        if not HAS_HTMLFRAME:
            st = scrolledtext.ScrolledText(self.web_tab, height=12)
            st.pack(fill="both", expand=True, padx=6, pady=(6,8))
            st.insert(tk.END, "未检测到 tkinterweb，无法嵌入网页。\n请使用上方搜索或点击“在外部浏览器打开”。")
            st.config(state="disabled")
            self.browser = None
            return

        # HtmlFrame init
        try:
            self.browser = HtmlFrame(self.web_tab, messages_enabled=False)
        except Exception:
            try:
                self.browser = HtmlFrame(self.web_tab)
            except Exception:
                self.browser = None
        
        if not self.browser:
            ttk.Label(self.web_tab, text="嵌入浏览器不可用", foreground="#c00").pack(expand=True)
            return

        if not init_only:
            try:
                if hasattr(self.browser, 'load_website'):
                    self.browser.load_website("https://www.bing.com/search?q=minecraft+crash+solutions")
                elif hasattr(self.browser, 'load_url'):
                    self.browser.load_url("https://www.bing.com/search?q=minecraft+crash+solutions")
            except Exception as e:
                print(f"[MainNotebook] Failed to load website: {e}")
        else:
            try:
                # tkinterweb uses different method names depending on version
                html = "<h3>在线解决方案：输入查询并点击 搜索 或 使用外部浏览器。</h3>"
                if hasattr(self.browser, 'set_content'):
                    self.browser.set_content(html)
                elif hasattr(self.browser, 'load_html'):
                    self.browser.load_html(html)
                elif hasattr(self.browser, 'set_html'):
                    self.browser.set_html(html)
            except Exception as e:
                print(f"[MainNotebook] Failed to set browser content: {e}")
        
        self.browser.pack(fill="both", expand=True, padx=6, pady=(6,8))
