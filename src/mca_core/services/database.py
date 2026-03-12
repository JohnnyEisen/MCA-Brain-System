
import logging
import os
import sqlite3
import threading
import time
import queue
from datetime import datetime
from typing import Any, Optional, Callable

logger = logging.getLogger("mca_core.database")

class DatabaseManager:
    _instance = None
    _lock = threading.RLock()

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._write_queue = queue.Queue()
        self._shutdown_event = threading.Event()
        self._ensure_tables()
        self._apply_pragma()
        self._writer_thread = threading.Thread(target=self._writer_loop, name="DB-Writer-Thread", daemon=True)
        self._writer_thread.start()

    @classmethod
    def get_instance(cls, db_path: str = "mca_data.db"):
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(db_path)
            return cls._instance

    def shutdown(self):
        self._shutdown_event.set()
        self._write_queue.put(None)
        self._writer_thread.join(timeout=2.0)

    def _get_conn(self, timeout: float = 30.0) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=timeout)
        conn.row_factory = sqlite3.Row
        return conn

    def _writer_loop(self):
        writer_conn = None
        try:
            writer_conn = sqlite3.connect(self.db_path, timeout=60.0)
            writer_conn.execute("PRAGMA journal_mode=WAL;")
            writer_conn.execute("PRAGMA synchronous=NORMAL;")
            
            while not self._shutdown_event.is_set():
                try:
                    task = self._write_queue.get(timeout=1.0)
                    if task is None:
                        break
                    func, args, kwargs, result_queue = task
                    try:
                        res = func(writer_conn, *args, **kwargs)
                        if result_queue: result_queue.put(("success", res))
                    except Exception as e:
                        logger.error(f"DB Write Task Error: {e}", exc_info=True)
                        if result_queue: result_queue.put(("error", e))
                    self._write_queue.task_done()
                except queue.Empty:
                    continue
        except Exception as e:
            logger.error(f"DB Writer thread failed: {e}")
        finally:
            if writer_conn: writer_conn.close()

    def _queue_write(self, func: Callable, *args, wait: bool = False, **kwargs) -> Any:
        if wait:
            result_queue = queue.Queue()
            self._write_queue.put((func, args, kwargs, result_queue))
            status, res = result_queue.get()
            if status == "error": return -1
            return res
        else:
            self._write_queue.put((func, args, kwargs, None))
            return 1

    def _apply_pragma(self) -> None:
        pragma_statements = ["PRAGMA journal_mode=WAL;", "PRAGMA synchronous=NORMAL;", "PRAGMA foreign_keys=ON;", "PRAGMA busy_timeout=30000;", "PRAGMA cache_size=-64000;"]
        try:
            with self._get_conn() as conn:
                for pragma in pragma_statements: conn.execute(pragma)
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to apply PRAGMA settings: {e}")

    def _ensure_tables(self) -> None:
        def _create_tables(conn):
            schema_queries = ["CREATE TABLE IF NOT EXISTS crash_history (id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT, file_path TEXT, file_hash TEXT, loader_type TEXT, mod_count INTEGER, summary TEXT, raw_log_snippet TEXT)", "CREATE TABLE IF NOT EXISTS crash_causes (id INTEGER PRIMARY KEY AUTOINCREMENT, crash_id INTEGER, cause_type TEXT, description TEXT, confidence FLOAT, FOREIGN KEY(crash_id) REFERENCES crash_history(id) ON DELETE CASCADE)", "CREATE TABLE IF NOT EXISTS knowledge_patterns (id INTEGER PRIMARY KEY AUTOINCREMENT, pattern_signature TEXT UNIQUE, solution_text TEXT, hit_count INTEGER DEFAULT 0, is_verified BOOLEAN DEFAULT 0, source TEXT)", "CREATE TABLE IF NOT EXISTS mod_index (mod_id TEXT, version TEXT, loader TEXT, is_problematic BOOLEAN DEFAULT 0, last_seen TEXT, PRIMARY KEY (mod_id, version, loader))"]
            index_queries = ["CREATE INDEX IF NOT EXISTS idx_crash_created ON crash_history(created_at DESC)", "CREATE INDEX IF NOT EXISTS idx_crash_causes_crash_id ON crash_causes(crash_id)", "CREATE INDEX IF NOT EXISTS idx_mod_is_problematic ON mod_index(is_problematic)", "CREATE INDEX IF NOT EXISTS idx_mod_last_seen ON mod_index(last_seen)"]
            for query in schema_queries + index_queries: conn.execute(query)
            conn.commit()
        try:
            with self._get_conn() as conn: _create_tables(conn)
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")

    def _execute_read(self, query: str, params: tuple = ()) -> list[dict[str, Any]]:
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"DB Read Error: {e}")
            return []

    def write_analysis_result(self, file_path: str, summary: str, loader: str, mod_count: int, file_hash, causes: list, mods: list) -> int:
        def _task(conn, f_path, summ, lder, m_count, f_hash, cses, mds):
            cursor = conn.execute("INSERT INTO crash_history (created_at, file_path, summary, loader_type, mod_count, file_hash) VALUES (?, ?, ?, ?, ?, ?)", (datetime.now().isoformat(), f_path, summ, lder, m_count, f_hash))
            crash_id = cursor.lastrowid
            if crash_id and crash_id > 0 and cses: conn.executemany("INSERT INTO crash_causes (crash_id, cause_type, description, confidence) VALUES (?, ?, ?, ?)", [(crash_id, c.get("type"), c.get("desc"), c.get("confidence", 1.0)) for c in cses])
            if mds:
                now_str = datetime.now().isoformat()
                conn.executemany("INSERT INTO mod_index (mod_id, version, loader, last_seen) VALUES (?, ?, ?, ?) ON CONFLICT(mod_id, version, loader) DO UPDATE SET last_seen = excluded.last_seen", [(m.get("id"), m.get("version"), lder, now_str) for m in mds if m.get("id")])
            conn.commit()
            return crash_id if crash_id else -1
        return self._queue_write(_task, file_path, summary, loader, mod_count, file_hash, causes, mods, wait=True)

    def add_crash_record(self, file_path: str, summary: str, loader: str, mod_count: int, file_hash = None) -> int:
        def _task(conn):
            cursor = conn.execute("INSERT INTO crash_history (created_at, file_path, summary, loader_type, mod_count, file_hash) VALUES (?, ?, ?, ?, ?, ?)", (datetime.now().isoformat(), file_path, summary, loader, mod_count, file_hash))
            conn.commit()
            return cursor.lastrowid
        return self._queue_write(_task, wait=True)

    def add_crash_causes(self, crash_id: int, causes: list) -> None:
        if not causes or crash_id < 0: return
        def _task(conn):
            conn.executemany("INSERT INTO crash_causes (crash_id, cause_type, description, confidence) VALUES (?, ?, ?, ?)", [(crash_id, c.get("type"), c.get("desc"), c.get("confidence", 1.0)) for c in causes])
            conn.commit()
        self._queue_write(_task)

    def get_recent_history(self, limit: int = 20) -> list:
        return self._execute_read("SELECT * FROM crash_history ORDER BY created_at DESC LIMIT ?", (limit,))

    def learn_pattern(self, signature: str, solution: str, source: str = "auto_learn") -> int:
        def _task(conn):
            cursor = conn.execute("INSERT INTO knowledge_patterns (pattern_signature, solution_text, hit_count, source) VALUES (?, ?, 1, ?) ON CONFLICT(pattern_signature) DO UPDATE SET hit_count = hit_count + 1, solution_text = excluded.solution_text", (signature, solution, source))
            conn.commit()
            return cursor.lastrowid
        return self._queue_write(_task, wait=True)

    def update_mod_index(self, mods: list, loader: str) -> None:
        if not mods: return
        def _task(conn):
            now_str = datetime.now().isoformat()
            data = [(m.get("id"), m.get("version"), loader, now_str) for m in mods if m.get("id")]
            conn.executemany("INSERT INTO mod_index (mod_id, version, loader, last_seen) VALUES (?, ?, ?, ?) ON CONFLICT(mod_id, version, loader) DO UPDATE SET last_seen = excluded.last_seen", data)
            conn.commit()
        self._queue_write(_task)

    def get_problematic_mods(self) -> list:
        return self._execute_read("SELECT mod_id, version, loader FROM mod_index WHERE is_problematic = 1")
