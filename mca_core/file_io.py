"""具有流式支持的文件 I/O 工具，用于减少内存占用。"""
from __future__ import annotations
import os
from typing import Iterable, Generator
from config.constants import DEFAULT_MAX_BYTES


def read_text_stream(path: str, chunk_size: int = 1024 * 256) -> Generator[str, None, None]:
    """分块产生文件内容，以支持大型日志而不会导致巨大的 RAM 峰值。"""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            yield data


def read_text_limited(path: str, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
    """智能加载：如果文件太大，加载通常包含崩溃信息的头部和尾部。
    
    策略：
    1. 如果大小 < max_bytes：全量加载。
    2. 如果大小 > max_bytes：加载 max_bytes 的前 50% 和后 50%。
       插入一个 '...[TRUNCATED]...' 标记。
    """
    try:
        size = os.path.getsize(path)
        if size <= max_bytes:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        
        # 大文件策略
        half = max_bytes // 2
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(half)
            
            # 定位到尾部
            f.seek(max(0, size - half), os.SEEK_SET)
            tail = f.read()
            
            return f"{head}\n\n...[FILE TRUNCATED {size} bytes -> {len(head)+len(tail)} bytes detected]...\n\n{tail}"
    except Exception:
        # 回退到简单读取
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_bytes)


def read_text_head(path: str, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
    """快速读取文件头部内容（避免尾部 seek），适合只需崩溃上下文的场景。"""
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_bytes)
    except Exception:
        return ""


def iter_lines(path: str) -> Iterable[str]:
    """用于流式处理的惰性行迭代器。"""
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            yield line
