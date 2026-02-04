from __future__ import annotations

# 支持两种启动方式：
# 1) 推荐：python -m brain_system.ui
# 2) 兼容：python brain_system/ui.py（仅修正 sys.path 以支持绝对导入）
import os
import sys

if __name__ == "__main__" and (__package__ is None or __package__ == ""):
    # 确保项目根目录在 sys.path 以支持 `brain_system.*` 绝对导入，避免二次 run_module。
    current_dir = os.path.abspath(os.path.dirname(__file__))
    project_root = os.path.abspath(os.path.dirname(current_dir))
    if not sys.path or os.path.abspath(str(sys.path[0])) != project_root:
        sys.path.insert(0, project_root)

import asyncio
import threading
import time
from concurrent.futures import Future
from dataclasses import dataclass
from typing import Any, Optional


class AsyncioLoopThread:
    """在后台线程运行 asyncio event loop，用于与 Tkinter 主线程协作。"""

    def __init__(self):
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._stop = threading.Event()

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            raise RuntimeError("async loop not started")
        return self._loop

    def start(self) -> None:
        if self._thread is not None:
            return

        def run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            self._ready.set()
            try:
                loop.run_forever()
            finally:
                try:
                    pending = asyncio.all_tasks(loop)
                    for t in pending:
                        t.cancel()
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except Exception:
                    pass
                loop.close()

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=5)

    def submit(self, coro: Any) -> Future:
        if self._thread is None:
            self.start()
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop(self) -> None:
        if self._loop is None:
            return
        try:
            self._loop.call_soon_threadsafe(self._loop.stop)
        except Exception:
            pass


@dataclass(slots=True)
class UiConfig:
    refresh_ms: int = 1000


def run_ui(*, config_path: Optional[str] = None) -> int:
    """启动 Tkinter 桌面 UI（纯 Python）。"""

    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox, ttk
    except Exception as e:  # pragma: no cover
        raise RuntimeError("当前 Python 环境未提供 tkinter，无法启动桌面 UI") from e

    from brain_system.core import BrainCore

    loop_thread = AsyncioLoopThread()
    loop_thread.start()

    brain = BrainCore(config_path=config_path)
    if brain.config.get("auto_load_dlcs", True):
        brain.load_all_dlcs()

    # 在后台 loop 启动性能监控
    try:
        loop_thread.submit(_start_monitor(brain))
    except Exception:
        pass

    ui_cfg = UiConfig(refresh_ms=int(brain.config.get("ui_refresh_ms", 1000)))

    root = tk.Tk()
    root.title("brain-system UI")
    root.geometry("980x680")

    main = ttk.Frame(root, padding=10)
    main.pack(fill=tk.BOTH, expand=True)

    # ---- 顶部操作区 ----
    top = ttk.Frame(main)
    top.pack(fill=tk.X)

    status_var = tk.StringVar(value="ready")

    def on_load_dlc_file() -> None:
        path = filedialog.askopenfilename(title="选择 DLC .py 文件", filetypes=[("Python", "*.py")])
        if not path:
            return
        n = brain.load_dlc_file(path)
        messagebox.showinfo("DLC", f"已加载 {n} 个 DLC 类")
        refresh_all()

    def on_reload_dlc_file() -> None:
        path = filedialog.askopenfilename(title="选择 DLC .py 文件", filetypes=[("Python", "*.py")])
        if not path:
            return
        n = brain.reload_dlc_file(path)
        messagebox.showinfo("DLC", f"已热升级加载 {n} 个 DLC 类")
        refresh_all()

    def on_load_dlc_dir() -> None:
        d = filedialog.askdirectory(title="选择 DLC 目录")
        if not d:
            return

        try:
            pkg_dir = os.path.abspath(os.path.dirname(__file__))
            if os.path.abspath(d) == pkg_dir:
                messagebox.showwarning(
                    "提示",
                    "不要选择 brain_system 目录作为 DLC 目录。\n"
                    "请使用单独的 ./dlcs 目录放置可加载的 DLC 文件。",
                )
                return
        except Exception:
            pass

        n = brain.load_all_dlcs([d])
        messagebox.showinfo("DLC", f"从目录加载 {n} 个 DLC 类")
        refresh_all()

    ttk.Button(top, text="加载DLC文件", command=on_load_dlc_file).pack(side=tk.LEFT)
    ttk.Button(top, text="热升级DLC文件", command=on_reload_dlc_file).pack(side=tk.LEFT, padx=(8, 0))
    ttk.Button(top, text="加载DLC目录", command=on_load_dlc_dir).pack(side=tk.LEFT, padx=(8, 0))

    ttk.Label(top, textvariable=status_var).pack(side=tk.RIGHT)

    # ---- 中部：Notebook ----
    nb = ttk.Notebook(main)
    nb.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    # Tab 1: DLC
    tab_dlc = ttk.Frame(nb)
    nb.add(tab_dlc, text="DLC")

    cols = ("name", "version", "type", "enabled", "initialized", "deps")
    dlc_tree = ttk.Treeview(tab_dlc, columns=cols, show="headings")
    for c in cols:
        dlc_tree.heading(c, text=c)
        dlc_tree.column(c, width=120, stretch=True)
    dlc_tree.column("name", width=220)
    dlc_tree.column("deps", width=320)
    dlc_tree.pack(fill=tk.BOTH, expand=True)

    # Tab 2: Stats
    tab_stats = ttk.Frame(nb)
    nb.add(tab_stats, text="Stats")

    stats_text = tk.Text(tab_stats, height=20)
    stats_text.pack(fill=tk.BOTH, expand=True)

    # Tab 3: Cache
    tab_cache = ttk.Frame(nb)
    nb.add(tab_cache, text="Cache")

    cache_text = tk.Text(tab_cache, height=10)
    cache_text.pack(fill=tk.BOTH, expand=True)

    # Tab 4: Training
    tab_train = ttk.Frame(nb)
    nb.add(tab_train, text="Training")

    train_top = ttk.Frame(tab_train)
    train_top.pack(fill=tk.X)

    train_status = tk.StringVar(value="idle")
    ttk.Label(train_top, textvariable=train_status).pack(side=tk.LEFT)

    duration_var = tk.StringVar(value="20")
    concurrency_var = tk.StringVar(value="20")
    ttk.Label(train_top, text="duration(s)").pack(side=tk.LEFT, padx=(12, 4))
    ttk.Entry(train_top, width=6, textvariable=duration_var).pack(side=tk.LEFT)
    ttk.Label(train_top, text="concurrency").pack(side=tk.LEFT, padx=(12, 4))
    ttk.Entry(train_top, width=6, textvariable=concurrency_var).pack(side=tk.LEFT)

    train_log = tk.Text(tab_train, height=20)
    train_log.pack(fill=tk.BOTH, expand=True, pady=(10, 0))

    train_future: dict[str, Any] = {"f": None, "cancel": None}

    def _train_log(msg: str) -> None:
        train_log.insert(tk.END, msg + "\n")
        train_log.see(tk.END)

    def on_train_start() -> None:
        if train_future.get("f") is not None:
            return
        try:
            dur = float(duration_var.get().strip())
            conc = int(concurrency_var.get().strip())
        except Exception:
            messagebox.showerror("训练", "参数不合法")
            return

        from brain_system.training import BrainTrainer, TrainingConfig

        cancel = asyncio.Event()
        train_future["cancel"] = cancel
        train_status.set("running")
        _train_log("开始训练...")

        async def run_train():
            trainer = BrainTrainer()
            report = await trainer.train(
                brain,
                cfg=TrainingConfig(duration_seconds=dur, concurrency=conc),
                progress=_train_log,
                cancel_event=cancel,
            )
            return report

        f = loop_thread.submit(run_train())
        train_future["f"] = f

        def done_cb(_f):
            try:
                rep = _f.result()
                _train_log(
                    f"完成: total={rep.total_tasks} ok={rep.successes} fail={rep.failures} "
                    f"p50={rep.latencies_ms_p50:.1f}ms p95={rep.latencies_ms_p95:.1f}ms"
                )
                _train_log(f"建议配置: {rep.recommended_config}")
            except Exception as e:
                _train_log(f"训练失败: {e}")
            finally:
                train_status.set("idle")
                train_future["f"] = None
                train_future["cancel"] = None

        f.add_done_callback(lambda _f: root.after(0, lambda: done_cb(_f)))

    def on_train_stop() -> None:
        c = train_future.get("cancel")
        f = train_future.get("f")
        if c is not None:
            c.set()
            _train_log("请求停止训练...")
        if f is not None:
            try:
                f.cancel()
            except Exception:
                pass

    ttk.Button(train_top, text="开始训练", command=on_train_start).pack(side=tk.RIGHT)
    ttk.Button(train_top, text="停止", command=on_train_stop).pack(side=tk.RIGHT, padx=(0, 8))

    def refresh_dlc() -> None:
        for item in dlc_tree.get_children():
            dlc_tree.delete(item)
        st = brain.get_dlc_status()
        for name, info in sorted(st.items(), key=lambda x: x[0]):
            dlc_tree.insert(
                "",
                "end",
                values=(
                    name,
                    info.get("version"),
                    info.get("type"),
                    info.get("enabled"),
                    info.get("initialized"),
                    ",".join(info.get("dependencies", [])),
                ),
            )

    def refresh_stats() -> None:
        ps = dict(brain.performance_stats)
        lines = [
            f"name: {brain.name}",
            f"version: {brain.version}",
            "",
            "performance_stats:",
        ]
        for k, v in ps.items():
            lines.append(f"  - {k}: {v}")

        # 一些运行态信息
        lines.extend(
            [
                "",
                f"thread_pool_size: {brain.config.get('thread_pool_size')}",
                f"process_pool_size: {brain.config.get('process_pool_size')}",
                f"auto_load_dlcs: {brain.config.get('auto_load_dlcs')}",
            ]
        )

        stats_text.delete("1.0", tk.END)
        stats_text.insert(tk.END, "\n".join(lines))

    def refresh_cache() -> None:
        c = brain.result_cache
        lines = [
            f"entries: {len(c)}",
            f"max_entries: {c.max_entries}",
            f"ttl_seconds: {c.ttl_seconds}",
            "",
            f"hits: {getattr(c, 'hits', 0)}",
            f"misses: {getattr(c, 'misses', 0)}",
            f"evictions: {getattr(c, 'evictions', 0)}",
            f"expired: {getattr(c, 'expired', 0)}",
        ]
        cache_text.delete("1.0", tk.END)
        cache_text.insert(tk.END, "\n".join(lines))

    def refresh_all() -> None:
        refresh_dlc()
        refresh_stats()
        refresh_cache()

    last_refresh = {"t": 0.0}

    def tick() -> None:
        # UI 刷新
        try:
            refresh_all()
            last_refresh["t"] = time.time()
            status_var.set(f"updated {time.strftime('%H:%M:%S')}")
        except Exception as e:
            status_var.set(f"error: {e}")
        root.after(ui_cfg.refresh_ms, tick)

    closing = {"in_progress": False}

    def _force_shutdown() -> None:
        try:
            if brain.thread_pool:
                brain.thread_pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
        try:
            if brain.process_pool:
                brain.process_pool.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass

    def on_close() -> None:
        if closing["in_progress"]:
            return
        closing["in_progress"] = True
        status_var.set("closing...")

        def finalize() -> None:
            try:
                loop_thread.stop()
            except Exception:
                pass
            root.destroy()

        try:
            fut = loop_thread.submit(brain.shutdown())

            def done_cb(_f: Future) -> None:
                try:
                    _f.result(timeout=0)
                except Exception:
                    pass
                finalize()

            fut.add_done_callback(lambda _f: root.after(0, lambda: done_cb(_f)))

            def watchdog() -> None:
                if not fut.done():
                    _force_shutdown()
                    finalize()

            root.after(5000, watchdog)
        except Exception:
            _force_shutdown()
            finalize()

    root.protocol("WM_DELETE_WINDOW", on_close)

    # 初次刷新 + 定时刷新
    refresh_all()
    root.after(ui_cfg.refresh_ms, tick)

    root.mainloop()
    return 0


async def _start_monitor(brain: Any) -> None:
    try:
        brain.start_performance_monitor()
    except Exception:
        return


def main() -> int:
    import argparse
    import os

    p = argparse.ArgumentParser(prog="brain-ui")
    p.add_argument("--config", default=os.getenv("BRAIN_CONFIG", "config/brain_config.json"))
    args = p.parse_args()
    return int(run_ui(config_path=args.config))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        # 首次运行若收到控制台中断，避免回溯干扰体验
        raise SystemExit(130)
