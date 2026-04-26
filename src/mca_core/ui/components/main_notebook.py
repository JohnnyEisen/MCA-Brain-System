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
        self.plugin_tree = None
        self.plugin_status_var = None
        
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

        # 6. Plugin Management
        self.plugin_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.plugin_tab, text="插件管理")
        self._create_plugin_tab()

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

    def _create_plugin_tab(self):
        top = ttk.Frame(self.plugin_tab, padding=8)
        top.pack(fill="x")

        ttk.Label(top, text="插件与 DLC 状态", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(top, text="刷新", command=self._refresh_plugin_list).pack(side="right")
        ttk.Button(top, text="启用全部插件", command=self._enable_all_plugins).pack(side="right", padx=(0, 6))
        ttk.Button(top, text="启用所选", command=self._enable_selected_plugins).pack(side="right", padx=(0, 6))
        ttk.Button(top, text="禁用所选", command=self._disable_selected_plugins).pack(side="right", padx=(0, 6))

        self.plugin_status_var = tk.StringVar(value="正在加载插件状态...")
        ttk.Label(top, textvariable=self.plugin_status_var, foreground="#666666").pack(side="right", padx=(0, 8))

        body = ttk.Frame(self.plugin_tab, padding=(8, 0, 8, 8))
        body.pack(fill="both", expand=True)

        columns = ("name", "source", "kind", "status")
        self.plugin_tree = ttk.Treeview(body, columns=columns, show="headings", height=12)
        self.plugin_tree.heading("name", text="名称")
        self.plugin_tree.heading("source", text="来源")
        self.plugin_tree.heading("kind", text="类型")
        self.plugin_tree.heading("status", text="状态")
        self.plugin_tree.column("name", width=220, anchor="w")
        self.plugin_tree.column("source", width=260, anchor="w")
        self.plugin_tree.column("kind", width=90, anchor="center")
        self.plugin_tree.column("status", width=90, anchor="center")

        y_scroll = ttk.Scrollbar(body, orient="vertical", command=self.plugin_tree.yview)
        self.plugin_tree.configure(yscrollcommand=y_scroll.set)

        self.plugin_tree.pack(side="left", fill="both", expand=True)
        y_scroll.pack(side="right", fill="y")

        tip = (
            "说明: 当前版本插件为后端静默加载。此页面用于查看已加载项，"
            "不影响插件启停逻辑。"
        )
        ttk.Label(self.plugin_tab, text=tip, foreground="#777777", wraplength=900, padding=(8, 0, 8, 8)).pack(fill="x")

        self._refresh_plugin_list()

    def _refresh_plugin_list(self):
        if not self.plugin_tree:
            return

        for item in self.plugin_tree.get_children():
            self.plugin_tree.delete(item)

        total = 0
        disabled_plugins = getattr(self.app, "_disabled_plugins", set())

        # Registered Python plugins
        plugins = []
        try:
            registry = getattr(self.app, "plugin_registry", None)
            if registry and hasattr(registry, "list"):
                plugins = registry.list() or []
        except Exception:
            plugins = []

        for plugin in plugins:
            name = getattr(plugin, "__name__", "plugin_entry")
            source = getattr(plugin, "__module__", "unknown")
            plugin_key = f"{source}:{name}"
            status = "已禁用" if plugin_key in disabled_plugins else "已启用"
            self.plugin_tree.insert("", "end", iid=plugin_key, values=(name, source, "Plugin", status))
            total += 1

        # Loaded Brain DLC modules (if brain core initialized)
        try:
            brain = getattr(self.app, "brain", None)
            dlcs = getattr(brain, "dlcs", {}) if brain else {}
            if isinstance(dlcs, dict):
                for dlc_name, dlc_obj in dlcs.items():
                    source = getattr(dlc_obj, "__class__", type(dlc_obj)).__name__
                    dlc_key = f"dlc:{dlc_name}"
                    self.plugin_tree.insert("", "end", iid=dlc_key, values=(str(dlc_name), source, "DLC", "已启用"))
                    total += 1
        except Exception:
            pass

        if total == 0:
            self.plugin_tree.insert("", "end", values=("(无)", "-", "-", "未检测到"))
            self.plugin_status_var.set("未检测到已加载插件")
        else:
            self.plugin_status_var.set(f"共检测到 {total} 个已加载扩展")

    def _disable_selected_plugins(self):
        if not self.plugin_tree:
            return
        selected = self.plugin_tree.selection()
        if not selected:
            return

        disabled_plugins = getattr(self.app, "_disabled_plugins", set())
        changed = 0
        for item_id in selected:
            values = self.plugin_tree.item(item_id, "values")
            if len(values) < 3 or values[2] != "Plugin":
                continue
            disabled_plugins.add(item_id)
            changed += 1

        self.app._disabled_plugins = disabled_plugins
        self._refresh_plugin_list()
        if self.plugin_status_var and changed:
            self.plugin_status_var.set(f"已禁用 {changed} 个插件（会话级）")

    def _enable_selected_plugins(self):
        if not self.plugin_tree:
            return
        selected = self.plugin_tree.selection()
        if not selected:
            return

        disabled_plugins = getattr(self.app, "_disabled_plugins", set())
        changed = 0
        for item_id in selected:
            values = self.plugin_tree.item(item_id, "values")
            if len(values) < 3 or values[2] != "Plugin":
                continue
            if item_id in disabled_plugins:
                disabled_plugins.remove(item_id)
                changed += 1

        self.app._disabled_plugins = disabled_plugins
        self._refresh_plugin_list()
        if self.plugin_status_var and changed:
            self.plugin_status_var.set(f"已启用 {changed} 个插件（会话级）")

    def _enable_all_plugins(self):
        self.app._disabled_plugins = set()
        self._refresh_plugin_list()
        if self.plugin_status_var:
            self.plugin_status_var.set("所有插件已启用（会话级）")

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
