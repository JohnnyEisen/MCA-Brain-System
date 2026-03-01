from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List


class TaskExecutor:
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self._futures: List = []

    def submit_analysis_task(self, task_func: Callable, callback: Callable):
        future = self.executor.submit(task_func)
        self._futures.append(future)
        def _done(f):
            try:
                result = f.result()
                callback(result)
            except Exception:
                callback(None)
        future.add_done_callback(_done)
        return future

    def shutdown(self):
        for f in self._futures:
            if not f.done():
                f.cancel()
        self.executor.shutdown(wait=False)
