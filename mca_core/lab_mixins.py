import os
import threading
from datetime import datetime
import tkinter as tk
from tkinter import ttk, scrolledtext
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    from tools.generate_mc_log import generate_batch
    HAS_LOG_GENERATOR = True
except ImportError:
    generate_batch = None
    HAS_LOG_GENERATOR = False

# Torch removed from lab mixins for slimming
HAS_TORCH = False

from config.constants import BASE_DIR, LAB_HEAD_READ_SIZE

logger = logging.getLogger("mca_core.lab")

class LabMixin:
    """Mixin for Neural Core Lab (Adversarial Testing) UI and Logic."""

    def _create_auto_test_tab(self):
        try:
            for w in self.auto_test_tab.winfo_children():
                w.destroy()
        except Exception:
            pass

        # === Wrapper Frame with Scrollbar ===
        wrapper = ttk.Frame(self.auto_test_tab)
        wrapper.pack(fill="both", expand=True)
        
        canvas = tk.Canvas(wrapper, highlightthickness=0)
        scrollbar = ttk.Scrollbar(wrapper, orient="vertical", command=canvas.yview)
        main_frame = ttk.Frame(canvas, padding=8)
        
        main_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=main_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Enable MouseWheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # === Diagnostics Lab Header ===
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Label(header_frame, text="Diagnostics Lab", font=("Segoe UI", 16, "bold"), foreground="#2c3e50").pack(side="left")
        ttk.Label(header_frame, text=" | 场景生成与全链路压测", font=("Microsoft YaHei UI", 10), foreground="#7f8c8d").pack(side="left", padx=5, pady=(5,0))

        # 底部状态信息 (Moved up for layout)
        status_frame = ttk.Frame(header_frame)
        status_frame.pack(side="right")

        # Analyzer Badge
        ana_color = "#3498db" # Blue
        pattern_count = 0
        if hasattr(self, 'crash_pattern_learner') and self.crash_pattern_learner:
            pattern_count = self.crash_pattern_learner.get_pattern_count()
        ana_txt = f"蓝方 (Analyzer): 就绪 (库容量: {pattern_count})"
        ttk.Label(status_frame, text="⬤ " + ana_txt, foreground=ana_color, font=("Microsoft YaHei UI", 9, "bold")).pack(side="right", padx=10)

        if not HAS_LOG_GENERATOR:
            ttk.Label(main_frame, text="未检测到日志生成器 (tools/generate_mc_log.py)。", foreground="#c00").pack(anchor="w")
            return

        # === Adversarial Control Panel ===
        
        # Vars (Initialize if needed)
        if not hasattr(self, "lab_mode_var"):
            self.lab_mode_var = tk.StringVar(value="adversarial")
            self.lab_count_var = tk.IntVar(value=5)
            self.lab_status_var = tk.StringVar(value="等待指令...")
            self.lab_running = False

        ctrl_frame = ttk.LabelFrame(main_frame, text="对抗生成控制台", padding=10)
        ctrl_frame.pack(fill="x", pady=(0, 10))
        
        # Row 1: Attack Vector Selection
        ttk.Label(ctrl_frame, text="攻击向量:").grid(row=0, column=0, sticky="w", pady=5)
        
        vectors = [
            ("混合对抗 (Adversarial)", "adversarial"),
            ("内存溢出 (OOM)", "oom"),
            ("显存/渲染 (GL Error)", "gl_error"), 
            ("依赖缺失 (Dependency)", "missing_dependency"),
            ("版本冲突 (Version)", "version_conflict")
        ]
        
        vec_frame = ttk.Frame(ctrl_frame)
        vec_frame.grid(row=0, column=1, columnspan=3, sticky="w")
        
        for txt, val in vectors:
            ttk.Radiobutton(vec_frame, text=txt, variable=self.lab_mode_var, value=val).pack(side="left", padx=5)

        # Row 2: Intensity
        ttk.Label(ctrl_frame, text="生成批次:").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Scale(ctrl_frame, from_=1, to=50, variable=self.lab_count_var, orient="horizontal", length=200).grid(row=1, column=1, sticky="w", padx=5)
        ttk.Label(ctrl_frame, textvariable=self.lab_count_var).grid(row=1, column=2, sticky="w")
        
        # Action Button
        def _run_lab_test():
            if self.lab_running: return
            self.lab_running = True
            threading.Thread(target=self._run_lab_task, daemon=True).start()

        btn = ttk.Button(ctrl_frame, text="运行测试 (Inject Faults)", command=_run_lab_test)
        btn.grid(row=1, column=3, padx=20, sticky="e")

        # === Run Log ===
        log_frame = ttk.LabelFrame(main_frame, text="测试运行日志", padding=10)
        log_frame.pack(fill="both", expand=True, pady=(0, 10))
        
        self.lab_log = scrolledtext.ScrolledText(log_frame, height=12, state="disabled", font=("Consolas", 9), background="#000000", foreground="#00ff00")
        self.lab_log.pack(fill="both", expand=True)

        # Tag config
        self.lab_log.tag_config("system", foreground="#bdc3c7")
        self.lab_log.tag_config("adv", foreground="#e74c3c") # Red for attacker
        self.lab_log.tag_config("def", foreground="#3498db") # Blue for defender
        self.lab_log.tag_config("success", foreground="#2ecc71")
        self.lab_log.tag_config("fail", foreground="#e67e22")

    def _log_lab(self, msg, tag="system"):
        if not hasattr(self, 'lab_log'): return
        self.root.after(0, lambda: self._log_lab_safe(msg, tag))

    def _log_lab_safe(self, msg, tag):
        try:
            self.lab_log.config(state="normal")
            ts = datetime.now().strftime("%H:%M:%S")
            self.lab_log.insert(tk.END, f"[{ts}] {msg}\n", tag)
            self.lab_log.see(tk.END)
            self.lab_log.config(state="disabled")
        except Exception:
            pass

    def _run_lab_task(self):
        scenario = self.lab_mode_var.get()
        count = self.lab_count_var.get()
        out_dir = os.path.join(BASE_DIR, "analysis_data", "lab_runs")
        
        scenario_map = {
            "adversarial": "混合对抗",
            "oom": "内存溢出",
            "gl_error": "显存/渲染错误",
            "missing_dependency": "依赖缺失",
            "version_conflict": "版本冲突"
        }
        scenario_cn = scenario_map.get(scenario, scenario)

        self._log_lab(f"启动对抗生成引擎... 目标: {scenario_cn}, 数量: {count}", "adv")
        
        try:
             # 1. Generate
             summary = generate_batch(
                output_dir=out_dir,
                target_bytes=512*1024,
                seed=None,
                scenarios=[scenario],
                count=count,
                report_path=None
            )
             self._log_lab(f"生成完成。共 {len(summary)} 个样本。", "adv")
             
             # 2. Analyze
             success_count = 0
             try:
                from mca_core.idle_trainer import HeadlessAnalyzer
             except ImportError:
                self._log_lab("错误: 找不到 HeadlessAnalyzer 模块。", "fail")
                return

             # 预热：在主线程初始化一次 HeadlessAnalyzer 以触发 DetectorRegistry 的类加载
             # 这能防止多线程并行 import 时发生的死锁或竞争条件
             try:
                 self._log_lab("核心组件预热中...", "def")
                 # 传入 None 作为 learner 仅用于触发 registry 加载
                 warmup = HeadlessAnalyzer(None, head_only=True)
                 del warmup
             except Exception as e:
                 logger.warning(f"预热失败: {e}")

             # Define worker for parallel execution
             def _analyze_worker(idx, item, learner):
                 f_path = item["file"]
                 f_name = os.path.basename(f_path)
                 # Create a fresh analyzer for this thread with reduced log size (head-only)
                 analyzer = HeadlessAnalyzer(learner, max_bytes=LAB_HEAD_READ_SIZE, head_only=True)
                 found = analyzer.run_cycle(f_path)
                 return idx, f_name, found, dict(analyzer.cause_counts), analyzer.analysis_results

             # Launch thread pool
             max_workers = os.cpu_count() or 4
             self._log_lab(f"启动并行分析 (线程数: {max_workers})...", "def")
             
             with ThreadPoolExecutor(max_workers=max_workers) as executor:
                 futures = []
                 for i, item in enumerate(summary):
                     # Learner handling could be tricky with threads if not thread-safe
                     # Assuming read-only access for classification or simple updates
                     futures.append(executor.submit(_analyze_worker, i+1, item, self.crash_pattern_learner))
                 
                 for future in as_completed(futures):
                     try:
                         idx, fname, is_success, causes, details = future.result()
                         if is_success:
                            if causes:
                                cause_str = ", ".join([f"{k}x{v}" for k,v in causes.items()])
                                self._log_lab(f"[{idx}/{count}] {fname} -> 拦截成功! ({cause_str})", "success")
                            else:
                                self._log_lab(f"[{idx}/{count}] {fname} -> 拦截成功! (未知归类)", "success")
                            
                            # 输出详细诊断信息（过滤掉无用信息）
                            if details:
                                # 筛选有效的诊断信息行
                                display_lines = []
                                for d in details:
                                    d = d.rstrip()
                                    if not d: continue
                                    # 排除一些非核心的统计行
                                    if any(skip in d for skip in ["扫描完成", "Mod总数", "加载器:"]):
                                        continue
                                    display_lines.append(d)

                                # 展示前 N 行 (确保有足够的上下文: 标题 + 内容)
                                max_show = 8  # 增加显示行数，确保能看到具体的缺失MOD
                                for i, line in enumerate(display_lines):
                                    if i >= max_show:
                                        self._log_lab(f"      ... (还有 {len(display_lines) - max_show} 条详情)", "def")
                                        break
                                    
                                    # 简单的格式化：保留缩进层级感
                                    clean_line = line.strip()
                                    if clean_line.startswith("-") or line.startswith("  "):
                                         self._log_lab(f"      {clean_line}", "def")
                                    else:
                                         self._log_lab(f"    > {clean_line}", "def")

                            success_count += 1
                         else:
                            self._log_lab(f"[{idx}/{count}] {fname} -> 拦截失败!", "fail")
                     except Exception as exc:
                         self._log_lab(f"分析异常: {exc}", "fail")

             self._log_lab(f"对抗测试结束. 成功防御率: {success_count}/{count}", "system")

        except Exception as e:
            self._log_lab(f"运行时错误: {e}", "fail")
        finally:
            self.lab_running = False
