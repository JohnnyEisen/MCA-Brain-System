from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import multiprocessing
import os
import pickle
import time
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set, Tuple

from packaging.specifiers import SpecifierSet
from packaging.version import Version

from .discovery import iter_dlc_files, load_dlc_classes_from_file
from .dlc import BrainDLC
from .models import DLCManifest

from .cache import LruTtlCache
from .observability import build_observability, start_span
from .retry import RetryPolicy, async_retry
from .security import SignatureVerificationError, load_public_keys_from_files, verify_dlc_signature
from .config import ConsulConfigSource, FileConfigSource
from .ha import LeaderElectionConfig, LeaderElector


try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover
    psutil = None


def _invoke_callable(func: Callable[..., Any], args: tuple[Any, ...], kwargs: Dict[str, Any]) -> Any:
    """在进程池中执行可序列化调用。"""
    return func(*args, **kwargs)


class BrainCore:
    """大脑核心类：任务调度 + DLC 管理 + 可选监控。"""

    def __init__(self, config_path: Optional[str] = None):
        self.name = "Brain Core"
        self.version = "1.0.0"

        self._config_path = config_path
        self.config = self._load_config(config_path)
        self._setup_logging()

        self.obs = build_observability(self.config)

        self._public_keys_pem: list[bytes] = []
        self._load_public_keys()

        self.dlcs: Dict[str, BrainDLC] = {}
        self.dlc_manifests: Dict[str, DLCManifest] = {}
        self.dlc_dependencies: Dict[str, Set[str]] = {}

        self.computational_units: Dict[str, Any] = {}
        self.result_cache = LruTtlCache(
            max_entries=int(self.config.get("cache_max_entries", 10_000)),
            ttl_seconds=float(self.config.get("cache_ttl_seconds", 300.0)),
        )

        self.performance_stats: Dict[str, Any] = {
            "total_tasks": 0,
            "completed_tasks": 0,
            "avg_compute_time": 0.0,
            "memory_usage": 0.0,
            "cpu_usage": 0.0,
        }

        self.monitor_task: Optional[asyncio.Task[None]] = None

        # 资源池（兼容 DLC 直接使用 thread_pool/process_pool 的写法）
        self.thread_pool = ThreadPoolExecutor(max_workers=int(self.config.get("thread_pool_size", 50)))
        process_pool_size = int(self.config.get("process_pool_size", multiprocessing.cpu_count()))
        self.process_pool = ProcessPoolExecutor(max_workers=process_pool_size) if process_pool_size > 0 else None

        self.retry_policy = RetryPolicy(
            max_attempts=int(self.config.get("retry_max_attempts", 1)),
            initial_delay_seconds=float(self.config.get("retry_initial_delay_seconds", 0.2)),
            max_delay_seconds=float(self.config.get("retry_max_delay_seconds", 5.0)),
            backoff_multiplier=float(self.config.get("retry_backoff_multiplier", 2.0)),
            jitter_ratio=float(self.config.get("retry_jitter_ratio", 0.2)),
        )

        self._config_source = self._build_config_source()
        if self._config_source is not None and bool(self.config.get("enable_config_watch", False)):
            self._config_source.start_watch(self._on_config_update)

        self._leader_elector = self._build_leader_elector()
        if self._leader_elector is not None:
            try:
                self._leader_elector.start()
            except Exception:
                pass

        if self.config.get("enable_disk_cache", True):
            self._setup_disk_cache()

        logging.info("%s v%s 初始化完成", self.name, self.version)

    # ---------------- 配置 / 日志 ----------------

    def _load_config(self, config_path: Optional[str]) -> Dict[str, Any]:
        default_config: Dict[str, Any] = {
            "thread_pool_size": 50,
            "process_pool_size": multiprocessing.cpu_count(),
            "enable_disk_cache": True,
            "cache_size_mb": 256,
            "cache_max_entries": 10_000,
            "cache_ttl_seconds": 300,
            "log_level": "INFO",
            "log_json": False,
            "monitoring_interval": 5.0,
            "auto_load_dlcs": True,
            "dlc_search_paths": ["./dlcs"],
            "dlc_strict_dependency_check": True,

            # DLC 安全
            "dlc_signature_required": False,
            "dlc_signature_verify_if_present": True,
            "dlc_public_key_pem_files": [],

            # 可观测性
            "enable_metrics": False,
            "enable_tracing": False,
            "service_name": "brain",

            # 重试
            "retry_max_attempts": 1,

            # 配置热更新（可选）
            "enable_config_watch": False,
            "config_source": "file",  # file|consul
            "config_poll_seconds": 1.0,
            "consul_host": "127.0.0.1",
            "consul_port": 8500,
            "consul_key_prefix": "brain/config",

            # HA（可选）
            "leader_election_enabled": False,
            "redis_url": "redis://localhost:6379/0",
            "leader_lock_key": "brain:leader",
        }

        if config_path and os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    user_config = json.load(f)
                if isinstance(user_config, dict):
                    default_config.update(user_config)
            except Exception as e:
                logging.warning("加载配置文件失败: %s", e)

        return default_config

    def _parse_dependency(self, raw: str) -> tuple[str, SpecifierSet]:
        """解析依赖声明。

        支持：
        - "Brain Core"（无版本约束）
        - "Brain Core>=1.0.0,<2"（语义化版本约束）
        """

        s = str(raw).strip()
        if not s:
            return "", SpecifierSet("")

        first_op = None
        for i, ch in enumerate(s):
            if ch in "<>=!~":
                first_op = i
                break

        if first_op is None:
            return s, SpecifierSet("")

        name = s[:first_op].strip()
        spec = s[first_op:].strip()
        return name, SpecifierSet(spec)

    def _validate_dependency(self, dep_raw: str) -> None:
        name, spec = self._parse_dependency(dep_raw)
        if not name:
            raise RuntimeError("依赖声明为空")

        # 允许依赖声明指向核心本体（不是 DLC）。
        # 常见写法："Brain Core"。
        core_aliases = {self.name, "Brain Core", "BrainCore", "core"}
        if name in core_aliases:
            if str(spec):
                try:
                    ver = Version(str(self.version))
                except Exception as e:
                    raise RuntimeError(f"核心版本不可解析: {self.version}") from e
                if ver not in spec:
                    raise RuntimeError(f"核心版本不兼容: {ver} not in {spec}")
            return

        if name not in self.dlc_manifests:
            raise RuntimeError(f"缺少依赖 DLC: {name}")

        if str(spec):
            try:
                ver = Version(str(self.dlc_manifests[name].version))
            except Exception as e:
                raise RuntimeError(f"依赖 DLC 版本不可解析: {name}={self.dlc_manifests[name].version}") from e

            if ver not in spec:
                raise RuntimeError(f"依赖 DLC 版本不兼容: {name}={ver} not in {spec}")

    def _setup_logging(self) -> None:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        level_name = self.config.get("log_level", "INFO")
        level = getattr(logging, str(level_name).upper(), logging.INFO)

        handlers = [logging.StreamHandler()]
        try:
            handlers.append(
                RotatingFileHandler(
                    "brain_core.log",
                    maxBytes=10 * 1024 * 1024,
                    backupCount=5,
                    encoding="utf-8",
                )
            )
        except Exception:
            # 文件系统不可写时，至少保留 stdout
            pass

        # 结构化 JSON 日志（可选依赖）
        if bool(self.config.get("log_json", False)):
            try:
                from pythonjsonlogger import jsonlogger  # type: ignore

                fmt = jsonlogger.JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s")
                for h in handlers:
                    h.setFormatter(fmt)
                logging.basicConfig(level=level, handlers=handlers)
                return
            except Exception:
                pass

        logging.basicConfig(level=level, format=log_format, handlers=handlers)

    def _set_log_level(self, level_name: str) -> None:
        level = getattr(logging, str(level_name).upper(), logging.INFO)
        logging.getLogger().setLevel(level)

    def _load_public_keys(self) -> None:
        files = self.config.get("dlc_public_key_pem_files", [])
        if isinstance(files, list) and files:
            try:
                self._public_keys_pem = load_public_keys_from_files([str(x) for x in files])
            except Exception as e:
                logging.warning("加载 DLC 公钥失败: %s", e)

    def _verify_dlc_file_signature(self, path: Path) -> bool:
        """在 import/exec 之前验证 DLC 文件签名。"""

        try:
            required = bool(self.config.get("dlc_signature_required", False))
            verify_if_present = bool(self.config.get("dlc_signature_verify_if_present", True))
            sig_exists = Path(str(path) + ".sig").exists()
            if required or (verify_if_present and sig_exists):
                if not self._public_keys_pem:
                    raise SignatureVerificationError("未配置 dlc_public_key_pem_files")
                verify_dlc_signature(path, public_keys_pem=self._public_keys_pem)
            return True
        except SignatureVerificationError as e:
            logging.error("DLC 签名验证失败，拒绝加载 %s: %s", str(path), e)
            return False
        except Exception as e:
            logging.error("DLC 签名验证异常，拒绝加载 %s: %s", str(path), e)
            return False

    def _build_config_source(self):
        src = str(self.config.get("config_source", "file")).lower()
        if src == "consul":
            try:
                return ConsulConfigSource(
                    host=str(self.config.get("consul_host", "127.0.0.1")),
                    port=int(self.config.get("consul_port", 8500)),
                    key_prefix=str(self.config.get("consul_key_prefix", "brain/config")),
                    poll_seconds=float(self.config.get("config_poll_seconds", 2.0)),
                )
            except Exception as e:
                logging.warning("Consul 配置源不可用: %s", e)
                return None

        # 默认 file
        if self._config_path and os.path.exists(self._config_path):
            return FileConfigSource(self._config_path, poll_seconds=float(self.config.get("config_poll_seconds", 1.0)))
        return None

    def _on_config_update(self, new_config: dict[str, Any]) -> None:
        # merge + apply
        if not isinstance(new_config, dict):
            return
        self.config.update(new_config)

        try:
            self._set_log_level(str(self.config.get("log_level", "INFO")))
        except Exception:
            pass

        try:
            self.result_cache.set_limits(
                max_entries=int(self.config.get("cache_max_entries", self.result_cache.max_entries)),
                ttl_seconds=float(self.config.get("cache_ttl_seconds", self.result_cache.ttl_seconds)),
            )
        except Exception:
            pass

        try:
            self.retry_policy = RetryPolicy(
                max_attempts=int(self.config.get("retry_max_attempts", self.retry_policy.max_attempts)),
                initial_delay_seconds=float(
                    self.config.get("retry_initial_delay_seconds", self.retry_policy.initial_delay_seconds)
                ),
                max_delay_seconds=float(self.config.get("retry_max_delay_seconds", self.retry_policy.max_delay_seconds)),
                backoff_multiplier=float(
                    self.config.get("retry_backoff_multiplier", self.retry_policy.backoff_multiplier)
                ),
                jitter_ratio=float(self.config.get("retry_jitter_ratio", self.retry_policy.jitter_ratio)),
            )
        except Exception:
            pass

        # 公钥可能变化
        self._load_public_keys()
        logging.info("配置已热更新")

    def _build_leader_elector(self) -> Optional[LeaderElector]:
        if not bool(self.config.get("leader_election_enabled", False)):
            return None
        try:
            cfg = LeaderElectionConfig(
                enabled=True,
                redis_url=str(self.config.get("redis_url", "redis://localhost:6379/0")),
                lock_key=str(self.config.get("leader_lock_key", "brain:leader")),
                ttl_seconds=int(self.config.get("leader_ttl_seconds", 10)),
                renew_interval_seconds=float(self.config.get("leader_renew_interval_seconds", 3.0)),
            )
            return LeaderElector(cfg)
        except Exception as e:
            logging.warning("Leader 选举不可用: %s", e)
            return None

    # ---------------- DLC 管理 ----------------

    def register_dlc(self, dlc: BrainDLC) -> None:
        manifest = dlc.get_manifest()

        if bool(self.config.get("dlc_strict_dependency_check", True)):
            for dep in manifest.dependencies:
                self._validate_dependency(dep)

        self.dlcs[manifest.name] = dlc
        self.dlc_manifests[manifest.name] = manifest
        self.dlc_dependencies[manifest.name] = set(manifest.dependencies)

        dlc.initialize()
        logging.info("已注册DLC: %s v%s", manifest.name, manifest.version)

    def unregister_dlc(self, name: str) -> None:
        dlc = self.dlcs.pop(name, None)
        self.dlc_manifests.pop(name, None)
        self.dlc_dependencies.pop(name, None)
        if dlc is not None:
            try:
                dlc.shutdown()
            except Exception:
                pass

    def reload_dlc_file(self, dlc_path: str) -> int:
        """热升级：卸载同名 DLC，再加载新版本。"""
        return self.load_dlc_file(dlc_path, allow_replace=True)

    def load_dlc_file(self, dlc_path: str, *, allow_replace: bool = False) -> int:
        """从文件加载 DLC，返回成功注册的 DLC 类数量。

        安全：支持 DLC 文件签名验证，避免动态加载任意代码执行。
        """
        path = Path(dlc_path)
        if not path.exists() or not path.is_file():
            return 0

        # DLC 签名验证必须发生在 import/exec 之前
        if not self._verify_dlc_file_signature(path):
            return 0

        try:
            classes = load_dlc_classes_from_file(path)
        except Exception as e:
            logging.error("加载DLC失败 %s: %s", dlc_path, e)
            return 0

        count = 0
        for cls in classes:
            try:
                inst = cls(self)
                manifest = inst.get_manifest()
                if allow_replace and manifest.name in self.dlcs:
                    self.unregister_dlc(manifest.name)
                self.register_dlc(inst)
                count += 1
            except Exception as e:
                logging.error("注册DLC失败 %s(%s): %s", path.name, cls.__name__, e)

        if self.obs.metrics_enabled and self.obs.dlc_loaded is not None:
            try:
                self.obs.dlc_loaded.inc(count)
            except Exception:
                pass
        return count

    def load_all_dlcs(self, search_paths: Optional[list[str]] = None) -> int:
        """从搜索路径加载 DLC。

        生产行为：
        - 尝试按 manifest.priority 升序注册
        - 多轮注册以解决依赖顺序问题
        """

        paths = search_paths or list(self.config.get("dlc_search_paths", ["./dlcs"]))
        dlc_files = iter_dlc_files(paths)

        # 避免把本包源码目录误选为 DLC 目录（会触发相对导入失败）
        try:
            package_dir = Path(__file__).resolve().parent
            dlc_files = [p for p in dlc_files if not p.resolve().is_relative_to(package_dir)]
        except Exception:
            # 兼容旧 Path API
            pass

        candidates: list[type[BrainDLC]] = []
        for file_path in dlc_files:
            # 安全：exec 之前必须验签
            if not self._verify_dlc_file_signature(file_path):
                continue
            try:
                classes = load_dlc_classes_from_file(file_path)
                candidates.extend(classes)
            except Exception as e:
                logging.error("读取 DLC 类失败 %s: %s", file_path, e)

        # 读取 manifest.priority 进行排序（实例化不会 initialize）
        scored: list[tuple[int, type[BrainDLC]]] = []
        for cls in candidates:
            try:
                inst = cls(self)
                scored.append((int(inst.get_manifest().priority), cls))
            except Exception:
                continue

        scored.sort(key=lambda x: x[0])
        pending = [c for _, c in scored]

        loaded = 0
        progressed = True
        while pending and progressed:
            progressed = False
            next_pending: list[type[BrainDLC]] = []
            for cls in pending:
                try:
                    inst = cls(self)
                    # allow_replace=False：避免静默替换，热升级用 reload_dlc_file
                    self.register_dlc(inst)
                    loaded += 1
                    progressed = True
                except Exception as e:
                    next_pending.append(cls)
                    logging.debug("DLC 延迟注册 %s: %s", getattr(cls, "__name__", str(cls)), e)
            pending = next_pending

        # 如果仍有 pending，输出明确错误
        for cls in pending:
            try:
                name = getattr(cls, "__name__", str(cls))
                inst = cls(self)
                manifest = inst.get_manifest()
                logging.error("DLC 注册失败(依赖未满足或版本冲突): %s deps=%s", name, manifest.dependencies)
            except Exception:
                logging.error("DLC 注册失败(无法解析 manifest): %s", getattr(cls, "__name__", str(cls)))

        logging.info("已加载 %d 个DLC类（来自 %d 个文件）", loaded, len(dlc_files))
        return loaded

    def get_dlc_status(self) -> Dict[str, Any]:
        status: Dict[str, Any] = {}
        for name, dlc in self.dlcs.items():
            manifest = self.dlc_manifests[name]
            status[name] = {
                "version": manifest.version,
                "type": manifest.dlc_type.value,
                "enabled": manifest.enabled,
                "dependencies": list(self.dlc_dependencies[name]),
                "initialized": bool(getattr(dlc, "_initialized", False)),
            }
        return status

    def get_computational_unit(self, unit_type: str) -> Any:
        if unit_type in self.computational_units:
            return self.computational_units[unit_type]

        for dlc in self.dlcs.values():
            units = dlc.provide_computational_units()
            if unit_type in units:
                self.computational_units[unit_type] = units[unit_type]
                return units[unit_type]

        raise ValueError(f"未找到计算单元类型: {unit_type}")

    # ---------------- 任务执行 / 缓存 ----------------

    async def compute(self, task_id: str, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        self.performance_stats["total_tasks"] += 1

        cache_key = self._generate_cache_key(func, *args, **kwargs)
        cached = self.result_cache.get(cache_key)
        if cached is not None:
            if self.obs.metrics_enabled and self.obs.cache_hits is not None:
                try:
                    self.obs.cache_hits.inc()
                except Exception:
                    pass
            return cached

        if self.obs.metrics_enabled and self.obs.cache_misses is not None:
            try:
                self.obs.cache_misses.inc()
            except Exception:
                pass

        async def _run_once() -> Any:
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)

            loop = asyncio.get_running_loop()

            # 兼容性策略：默认走线程池；可通过 task_id 前缀让 CPU 任务走进程池
            use_process = False
            cpu_prefixes = self.config.get("cpu_task_prefixes", ["cpu_", "cpu_task"])
            if isinstance(cpu_prefixes, list):
                for p in cpu_prefixes:
                    if str(task_id).startswith(str(p)):
                        use_process = True
                        break

            if use_process and self.process_pool is not None:
                return await loop.run_in_executor(self.process_pool, _invoke_callable, func, args, kwargs)

            return await loop.run_in_executor(self.thread_pool, _invoke_callable, func, args, kwargs)

        start_time = time.time()
        with start_span(self.obs, f"compute:{task_id}"):
            try:
                if self.retry_policy.max_attempts > 1:
                    result = await async_retry(_run_once, policy=self.retry_policy)
                else:
                    result = await _run_once()
            except Exception as e:
                if self.obs.metrics_enabled and self.obs.task_errors is not None:
                    try:
                        self.obs.task_errors.labels(task_id=str(task_id)).inc()
                    except Exception:
                        pass
                logging.error("计算任务失败 %s: %s", task_id, e)
                raise

        self.result_cache.set(cache_key, result)

        compute_time = time.time() - start_time
        if self.obs.metrics_enabled and self.obs.task_seconds is not None:
            try:
                self.obs.task_seconds.labels(task_id=str(task_id)).observe(compute_time)
            except Exception:
                pass

        self.performance_stats["completed_tasks"] += 1
        completed = self.performance_stats["completed_tasks"]
        prev_avg = float(self.performance_stats["avg_compute_time"])
        self.performance_stats["avg_compute_time"] = ((prev_avg * (completed - 1)) + compute_time) / completed

        return result

    def _generate_cache_key(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> str:
        func_name = getattr(func, "__name__", str(func))
        key_data = (func_name, args, tuple(sorted(kwargs.items())))
        return hashlib.md5(pickle.dumps(key_data)).hexdigest()

    # ---------------- 监控 / 生命周期 ----------------

    def start_performance_monitor(self) -> None:
        """启动性能监控。

        要求：必须在正在运行的事件循环中调用（即在 async 上下文里）。
        """

        async def monitor() -> None:
            while True:
                await asyncio.sleep(float(self.config.get("monitoring_interval", 5.0)))

                if psutil is not None:
                    try:
                        self.performance_stats["memory_usage"] = psutil.Process().memory_info().rss / 1024 / 1024
                        self.performance_stats["cpu_usage"] = psutil.cpu_percent()
                    except Exception:
                        pass

                for dlc in self.dlcs.values():
                    hook = getattr(dlc, "on_monitor_tick", None)
                    if callable(hook):
                        try:
                            hook(self.performance_stats)
                        except Exception as e:
                            logging.debug("DLC monitor hook 失败 %s: %s", dlc.get_manifest().name, e)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError as e:
            raise RuntimeError("start_performance_monitor() 必须在事件循环运行时调用") from e

        self.monitor_task = loop.create_task(monitor())

    async def shutdown(self) -> None:
        logging.info("正在关闭大脑系统...")

        if self.monitor_task:
            self.monitor_task.cancel()

        for dlc in list(self.dlcs.values()):
            try:
                dlc.shutdown()
            except Exception:
                pass

        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)
        if self.process_pool:
            self.process_pool.shutdown(wait=True)

        try:
            if self._config_source is not None:
                self._config_source.stop_watch()
        except Exception:
            pass

        try:
            if self._leader_elector is not None:
                self._leader_elector.stop()
        except Exception:
            pass

        self._save_cache()
        logging.info("大脑系统已关闭")

    # ---------------- 磁盘缓存 ----------------

    def _setup_disk_cache(self) -> None:
        cache_dir = Path.home() / ".brain" / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_dir = cache_dir
        self._cleanup_old_cache()
        self._load_cache()

    def _cleanup_old_cache(self) -> None:
        cache_files = list(self.cache_dir.glob("*.cache"))
        cache_files.sort(key=lambda x: x.stat().st_mtime)

        total_size = sum(f.stat().st_size for f in cache_files)
        max_size = int(self.config.get("cache_size_mb", 256)) * 1024 * 1024

        while total_size > max_size and cache_files:
            oldest = cache_files.pop(0)
            total_size -= oldest.stat().st_size
            try:
                oldest.unlink()
            except Exception:
                break

    def _load_cache(self) -> None:
        try:
            cache_path = Path(self.cache_dir) / "result_cache.json"
            if not cache_path.exists():
                return

            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            if isinstance(data, dict):
                self.result_cache.load_serializable(data)
        except Exception as e:
            logging.debug("加载磁盘缓存失败: %s", e)

    def _save_cache(self) -> None:
        try:
            if not self.config.get("enable_disk_cache", True):
                return
            if not getattr(self, "cache_dir", None):
                return

            cache_path = Path(self.cache_dir) / "result_cache.json"

            serializable = self.result_cache.snapshot_serializable()

            tmp_path = cache_path.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(serializable, f, ensure_ascii=False)
            tmp_path.replace(cache_path)
        except Exception as e:
            logging.debug("保存磁盘缓存失败: %s", e)
