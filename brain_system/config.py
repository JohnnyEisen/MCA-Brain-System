from __future__ import annotations

import json
import logging
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


ConfigListener = Callable[[dict[str, Any]], None]


@dataclass(slots=True)
class ConfigSource:
    """配置来源抽象。

    生产建议：优先外部配置中心；本项目提供 File watch + 可选 Consul。
    """

    def load(self) -> dict[str, Any]:  # pragma: no cover
        raise NotImplementedError

    def start_watch(self, listener: ConfigListener) -> None:  # pragma: no cover
        return

    def stop_watch(self) -> None:  # pragma: no cover
        return


class FileConfigSource(ConfigSource):
    def __init__(self, path: str, poll_seconds: float = 1.0):
        self._path = Path(path)
        self._poll_seconds = float(poll_seconds)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_mtime: Optional[float] = None

    def load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {}
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as e:
            logging.warning("配置文件解析失败: %s", e)
            return {}

    def start_watch(self, listener: ConfigListener) -> None:
        if self._thread is not None:
            return

        def run() -> None:
            while not self._stop.is_set():
                try:
                    if self._path.exists():
                        mtime = self._path.stat().st_mtime
                        if self._last_mtime is None:
                            self._last_mtime = mtime
                        elif mtime != self._last_mtime:
                            self._last_mtime = mtime
                            listener(self.load())
                except Exception:
                    pass
                time.sleep(self._poll_seconds)

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop_watch(self) -> None:
        self._stop.set()


class ConsulConfigSource(ConfigSource):
    def __init__(self, *, host: str, port: int, key_prefix: str, poll_seconds: float = 2.0):
        self._host = host
        self._port = int(port)
        self._key_prefix = key_prefix.rstrip("/")
        self._poll_seconds = float(poll_seconds)
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_index: Optional[int] = None

        try:
            import consul  # type: ignore
        except Exception as e:  # pragma: no cover
            raise RuntimeError("未安装 Consul 客户端，安装: pip install 'brain-system[config]'") from e

        self._consul = consul.Consul(host=self._host, port=self._port)

    def load(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        idx, items = self._consul.kv.get(self._key_prefix, recurse=True)
        self._last_index = idx
        if not items:
            return {}
        for it in items:
            key = it.get("Key")
            val = it.get("Value")
            if not key or val is None:
                continue
            try:
                rel = str(key)[len(self._key_prefix) + 1 :]
                data[rel] = json.loads(val.decode("utf-8"))
            except Exception:
                continue
        return data

    def start_watch(self, listener: ConfigListener) -> None:
        if self._thread is not None:
            return

        def run() -> None:
            while not self._stop.is_set():
                try:
                    idx, _ = self._consul.kv.get(self._key_prefix, recurse=True, index=self._last_index, wait="10s")
                    if idx and idx != self._last_index:
                        listener(self.load())
                except Exception:
                    pass
                time.sleep(self._poll_seconds)

        self._thread = threading.Thread(target=run, daemon=True)
        self._thread.start()

    def stop_watch(self) -> None:
        self._stop.set()
