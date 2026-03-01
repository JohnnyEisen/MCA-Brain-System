"""自动测试 Mixin - 批量生成+训练+评分

整合旧版自动测试功能，包括：
- 场景选择
- 批量生成测试日志
- 训练模式学习器
- 统计评分
"""

from __future__ import annotations
import os
import time
import threading
import logging
from collections import defaultdict, Counter
from typing import TYPE_CHECKING

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

from config.constants import BASE_DIR, LAB_HEAD_READ_SIZE, AUTO_TESTS_DIR
from config.constants import CAUSE_MEM, CAUSE_DEP, CAUSE_VER, CAUSE_GPU, CAUSE_OTHER

try:
    from tools.generate_mc_log import generate_batch, SCENARIOS
    from utils.parse_size import parse_size
    from mca_core.file_io import read_text_head
    HAS_LOG_GENERATOR = True
except ImportError:
    generate_batch = None
    SCENARIOS = {}
    parse_size = None
    read_text_head = None
    HAS_LOG_GENERATOR = False

try:
    from mca_core.idle_trainer import IdleTrainer
    HAS_IDLE_TRAINER = True
except ImportError:
    IdleTrainer = None
    HAS_IDLE_TRAINER = False

from mca_core.security import InputSanitizer
from mca_core.learning import CrashPatternLearner


class AutoTestMixin:
    """Mixin for legacy auto-test functionality."""

    def _init_auto_test_vars(self):
        if not hasattr(self, 'auto_test_size_var'):
            self.auto_test_size_var = tk.StringVar(value="2MB")
        if not hasattr(self, 'auto_test_count_var'):
            self.auto_test_count_var = tk.IntVar(value=10)
        if not hasattr(self, 'auto_test_seed_var'):
            self.auto_test_seed_var = tk.StringVar(value="")
        if not hasattr(self, 'auto_test_output_var'):
            self.auto_test_output_var = tk.StringVar(value=AUTO_TESTS_DIR)
        if not hasattr(self, 'auto_test_report_var'):
            self.auto_test_report_var = tk.StringVar(value="")
        if not hasattr(self, 'auto_test_train_var'):
            self.auto_test_train_var = tk.BooleanVar(value=True)
        if not hasattr(self, 'auto_test_cleanup_var'):
            self.auto_test_cleanup_var = tk.BooleanVar(value=True)
        if not hasattr(self, 'auto_test_isolated_var'):
            self.auto_test_isolated_var = tk.BooleanVar(value=False)
        
        for v in ['gen_time', 'train_time', 'total_time', 'hit_rate', 'fp_rate', 'samples', 'patterns']:
            attr = f'auto_test_{v}_var'
            if not hasattr(self, attr):
                setattr(self, attr, tk.StringVar(value="-"))

    def _create_legacy_auto_test_tab(self):
        """Create legacy auto-test UI (batch generation + training)."""
        try:
            for w in self.auto_test_tab.winfo_children():
                w.destroy()
        except Exception:
            pass
        
        main_frame = ttk.Frame(self.auto_test_tab, padding=10)
        main_frame.pack(fill="both", expand=True)
        
        self._init_auto_test_vars()
        
        # === Idle Trainer Section ===
        if HAS_IDLE_TRAINER and getattr(self, 'idle_trainer', None):
            idle_frame = ttk.LabelFrame(main_frame, text="闲置后台训练服务", padding=10)
            idle_frame.pack(fill="x", padx=4, pady=(0, 8))
            
            self.idle_enable_var = tk.BooleanVar(value=self.idle_trainer.enabled)
            self.idle_duration_hours = tk.StringVar(value=str(getattr(self.idle_trainer, 'duration_hours', 1)))
            self.idle_cpu_limit = tk.StringVar(value=str(getattr(self.idle_trainer, 'max_cpu', 20)))
            self.idle_ram_limit = tk.StringVar(value=str(getattr(self.idle_trainer, 'max_ram', 50)))
            self.idle_gpu_limit = tk.StringVar(value=str(getattr(self.idle_trainer, 'max_gpu', 30)))
            self.idle_trained_cnt = tk.StringVar(value="0")
            
            def _toggle_idle():
                if hasattr(self, 'idle_trainer') and self.idle_trainer:
                    self.idle_trainer.enabled = self.idle_enable_var.get()
            
            def _update_idle_cfg(*args):
                try:
                    if hasattr(self, 'idle_trainer') and self.idle_trainer:
                        self.idle_trainer.duration_hours = float(self.idle_duration_hours.get())
                        self.idle_trainer.max_cpu = float(self.idle_cpu_limit.get())
                        self.idle_trainer.max_ram = float(self.idle_ram_limit.get())
                        self.idle_trainer.max_gpu = float(self.idle_gpu_limit.get())
                except (ValueError, AttributeError):
                    pass
                
            def _refresh_idle_status():
                if getattr(self, 'idle_trainer', None):
                    self.idle_trained_cnt.set(str(getattr(self.idle_trainer, 'trained_count', 0)))
                self.root.after(2000, _refresh_idle_status)
            
            _refresh_idle_status()
            
            r1 = ttk.Frame(idle_frame)
            r1.pack(fill="x", pady=2)
            ttk.Checkbutton(r1, text="启用后台训练", variable=self.idle_enable_var, command=_toggle_idle).pack(side="left")
            ttk.Label(r1, text="持续时长(小时):").pack(side="left", padx=(15, 5))
            ttk.Entry(r1, textvariable=self.idle_duration_hours, width=5).pack(side="left")
            
            r2 = ttk.Frame(idle_frame)
            r2.pack(fill="x", pady=2)
            ttk.Label(r2, text="CPU<").pack(side="left")
            ttk.Entry(r2, textvariable=self.idle_cpu_limit, width=4).pack(side="left", padx=2)
            ttk.Label(r2, text="% RAM<").pack(side="left")
            ttk.Entry(r2, textvariable=self.idle_ram_limit, width=4).pack(side="left", padx=2)
            ttk.Label(r2, text="% GPU<").pack(side="left")
            ttk.Entry(r2, textvariable=self.idle_gpu_limit, width=4).pack(side="left", padx=2)
            ttk.Label(r2, text="%").pack(side="left")
            ttk.Label(r2, text="已训练:").pack(side="left", padx=(15, 5))
            ttk.Label(r2, textvariable=self.idle_trained_cnt, foreground="blue").pack(side="left")
            
            self.idle_duration_hours.trace_add("write", _update_idle_cfg)
            self.idle_cpu_limit.trace_add("write", _update_idle_cfg)
            self.idle_ram_limit.trace_add("write", _update_idle_cfg)
            self.idle_gpu_limit.trace_add("write", _update_idle_cfg)

        # === Scenario Selection ===
        scenario_frame = ttk.LabelFrame(main_frame, text="场景选择 (Ctrl/Shift多选)", padding=8)
        scenario_frame.pack(fill="x", pady=6)
        
        if SCENARIOS:
            scenario_names = [f"{k} - {v}" for k, v in SCENARIOS.items()]
        else:
            scenarios = {
                "normal": "正常日志", "version_conflict": "版本冲突", "missing_dependency": "缺失前置",
                "mixin_conflict": "Mixin注入失败", "ticking_entity": "实体更新错误",
                "out_of_memory": "内存溢出", "bad_video_driver": "显卡驱动不兼容",
            }
            scenario_names = [f"{k} - {v}" for k, v in scenarios.items()]

        self.auto_test_scenario_list = tk.Listbox(scenario_frame, selectmode="extended", height=4)
        for s in scenario_names:
            self.auto_test_scenario_list.insert(tk.END, s)
        self.auto_test_scenario_list.pack(side="left", fill="both", expand=True)
        scroller = ttk.Scrollbar(scenario_frame, orient="vertical", command=self.auto_test_scenario_list.yview)
        scroller.pack(side="right", fill="y")
        self.auto_test_scenario_list.config(yscrollcommand=scroller.set)
        self.auto_test_scenario_list.select_set(0, tk.END)

        # === Options ===
        opts_frame = ttk.Frame(main_frame)
        opts_frame.pack(fill="x", pady=4)
        ttk.Checkbutton(opts_frame, text="训练模式", variable=self.auto_test_train_var).pack(side="left", padx=6)
        ttk.Checkbutton(opts_frame, text="自动清理", variable=self.auto_test_cleanup_var).pack(side="left", padx=6)
        ttk.Checkbutton(opts_frame, text="使用隔离库", variable=self.auto_test_isolated_var).pack(side="left", padx=6)

        # === Action Buttons ===
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill="x", pady=4)
        self.auto_test_run_btn = ttk.Button(action_frame, text="开始", command=self._start_auto_test)
        self.auto_test_run_btn.pack(side="left")
        self.auto_test_stop_btn = ttk.Button(action_frame, text="停止", command=self._stop_auto_test, state="disabled")
        self.auto_test_stop_btn.pack(side="left", padx=6)
        self.auto_test_status_var = tk.StringVar(value="待机")
        ttk.Label(action_frame, textvariable=self.auto_test_status_var).pack(side="right")

        # === Progress ===
        self.auto_test_progress = ttk.Progressbar(main_frame, mode="determinate")
        self.auto_test_progress.pack(fill="x", pady=4)

        # === Stats ===
        stats_frame = ttk.LabelFrame(main_frame, text="统计", padding=8)
        stats_frame.pack(fill="x", pady=6)
        ttk.Label(stats_frame, text="生成耗时:").grid(row=0, column=0, sticky="w")
        ttk.Label(stats_frame, textvariable=self.auto_test_gen_time_var).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(stats_frame, text="训练耗时:").grid(row=0, column=2, sticky="w")
        ttk.Label(stats_frame, textvariable=self.auto_test_train_time_var).grid(row=0, column=3, sticky="w", padx=6)
        ttk.Label(stats_frame, text="命中率:").grid(row=1, column=0, sticky="w", pady=4)
        ttk.Label(stats_frame, textvariable=self.auto_test_hit_rate_var).grid(row=1, column=1, sticky="w", padx=6, pady=4)
        ttk.Label(stats_frame, text="样本数:").grid(row=1, column=2, sticky="w", pady=4)
        ttk.Label(stats_frame, textvariable=self.auto_test_samples_var).grid(row=1, column=3, sticky="w", padx=6, pady=4)

        # === Log ===
        self.auto_test_log = scrolledtext.ScrolledText(main_frame, height=6, state="disabled")
        self.auto_test_log.pack(fill="both", expand=True)

    def _start_auto_test(self):
        if not HAS_LOG_GENERATOR:
            messagebox.showerror("错误", "未安装日志生成器模块")
            return
        if getattr(self, "_auto_test_running", False):
            return

        try:
            count = int(self.auto_test_count_var.get())
            if count <= 0:
                raise ValueError
        except Exception:
            messagebox.showerror("参数错误", "数量必须为正整数")
            return

        selected = self.auto_test_scenario_list.curselection()
        scenarios = []
        for idx in selected:
            raw = self.auto_test_scenario_list.get(idx)
            scenarios.append(raw.split("-")[0].strip())
        if not scenarios:
            scenarios = ["normal"]

        output_dir = self.auto_test_output_var.get().strip() or AUTO_TESTS_DIR
        train = bool(self.auto_test_train_var.get())

        self._auto_test_cancel_event.clear()
        self._auto_test_running = True
        self.auto_test_run_btn.config(state="disabled")
        self.auto_test_stop_btn.config(state="normal")
        self.auto_test_progress.config(value=0, maximum=max(count, 1))
        self._auto_test_write_log("开始自动化测试...")
        self.auto_test_status_var.set("运行中")

        threading.Thread(
            target=self._auto_test_worker,
            args=(output_dir, scenarios, count, train),
            daemon=True,
        ).start()

    def _stop_auto_test(self):
        try:
            self._auto_test_cancel_event.set()
            self.auto_test_status_var.set("正在停止")
        except Exception:
            pass

    def _auto_test_worker(self, output_dir, scenarios, count, train):
        try:
            self._auto_test_write_log(f"生成日志：{count} 份，场景: {', '.join(scenarios)}")
            self.auto_test_status_var.set("生成中")
            t0 = time.time()

            summary = generate_batch(
                output_dir, 2*1024*1024, None, scenarios, count, None,
                cancel_cb=lambda: self._auto_test_cancel_event.is_set(),
            )
            if summary is None:
                summary = []
            gen_time = time.time() - t0
            self.root.after(0, lambda: self.auto_test_gen_time_var.set(self._format_duration(gen_time)))

            self._auto_test_write_log(f"生成完成，共 {len(summary)} 份日志")

            if train:
                self.auto_test_status_var.set("训练中")
                self.auto_test_progress.config(value=0, maximum=max(len(summary), 1))
                hit_count = 0

                for idx, item in enumerate(summary):
                    if self._auto_test_cancel_event.is_set():
                        self._auto_test_write_log("已请求停止，训练中止")
                        break
                    file_path = item.get("file")
                    try:
                        log_text = read_text_head(file_path, max_bytes=LAB_HEAD_READ_SIZE)
                    except Exception:
                        continue
                    
                    self._auto_test_write_log(f"[{idx+1}/{len(summary)}] 训练: {os.path.basename(file_path)}")
                    self._run_analysis_for_training(log_text, file_path, self.crash_pattern_learner)
                    hit_count += 1
                    self.root.after(0, lambda v=idx+1: self.auto_test_progress.config(value=v))

                self.root.after(0, lambda: self.auto_test_hit_rate_var.set(f"{hit_count}/{len(summary)}"))
                self.root.after(0, lambda: self.auto_test_samples_var.set(str(len(summary))))

            self._auto_test_write_log("自动化测试完成")

            if self.auto_test_cleanup_var.get() and summary:
                self._auto_test_write_log("正在清理生成的文件...")
                cnt = 0
                for item in summary:
                    try:
                        fp = item.get("file")
                        if fp and os.path.exists(fp):
                            os.remove(fp)
                            cnt += 1
                    except Exception:
                        pass
                self._auto_test_write_log(f"清理完成，删除了 {cnt} 个文件。")

        except Exception as e:
            self._auto_test_write_log(f"自动化测试失败: {e}")
        finally:
            self.root.after(0, self._auto_test_finish)

    def _auto_test_finish(self):
        self._auto_test_running = False
        try:
            self.auto_test_run_btn.config(state="normal")
            self.auto_test_stop_btn.config(state="disabled")
            self.auto_test_status_var.set("已完成")
        except Exception:
            pass

    def _auto_test_write_log(self, msg: str):
        def _write():
            try:
                self.auto_test_log.config(state="normal")
                self.auto_test_log.insert(tk.END, msg + "\n")
                self.auto_test_log.see(tk.END)
                self.auto_test_log.config(state="disabled")
            except Exception:
                pass
        self.root.after(0, _write)

    def _format_duration(self, seconds: float) -> str:
        try:
            if seconds < 1:
                ms = max(int(seconds * 1000), 1)
                return f"{ms}ms"
            return f"{seconds:.2f}s"
        except Exception:
            return "-"

    def _run_analysis_for_training(self, log_text: str, file_path: str, learner):
        self._is_auto_testing = True
        
        backup = {
            "crash_log": getattr(self, 'crash_log', ''),
            "file_path": getattr(self, 'file_path', ''),
            "analysis_results": list(getattr(self, 'analysis_results', [])),
            "mods": defaultdict(set, getattr(self, 'mods', defaultdict(set))),
            "mod_names": dict(getattr(self, 'mod_names', {})),
            "dependency_pairs": set(getattr(self, 'dependency_pairs', set())),
            "loader_type": getattr(self, 'loader_type', None),
            "cause_counts": Counter(getattr(self, 'cause_counts', Counter())),
            "file_checksum": getattr(self, 'file_checksum', None),
        }
        old_learner = self.crash_pattern_learner

        try:
            self.crash_log = log_text or ""
            self.file_path = file_path or ""
            self.file_checksum = None
            self.analysis_results = []
            self.mods = defaultdict(set)
            self.mod_names = {}
            self.dependency_pairs = set()
            self.loader_type = None
            self.cause_counts = Counter()
            self._invalidate_log_cache()
            self._graph_cache_key = None

            if learner is not None:
                self.crash_pattern_learner = learner

            self._run_analysis_logic()
            return {
                "analysis_results": list(self.analysis_results),
                "loader": self.loader_type,
                "cause_counts": dict(self.cause_counts),
            }
        except Exception as e:
            self._auto_test_write_log(f"训练分析失败: {e}")
        finally:
            self._is_auto_testing = False
            self.crash_pattern_learner = old_learner
            self.crash_log = backup["crash_log"]
            self.file_path = backup["file_path"]
            self.analysis_results = backup["analysis_results"]
            self.mods = backup["mods"]
            self.mod_names = backup["mod_names"]
            self.dependency_pairs = backup["dependency_pairs"]
            self.loader_type = backup["loader_type"]
            self.cause_counts = backup["cause_counts"]
            self.file_checksum = backup["file_checksum"]
