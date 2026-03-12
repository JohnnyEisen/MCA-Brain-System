"""统一的文件 I/O 工具模块。

提供流式读取、限制读取、原子写入等文件操作功能。
"""
from __future__ import annotations

import os
import shutil
from typing import Generator, Iterable

from config.constants import DEFAULT_MAX_BYTES, MAX_FILE_SIZE_HARD_LIMIT


# ==================== 流式读取 ====================


def read_text_stream(
    path: str, chunk_size: int = 1024 * 256
) -> Generator[str, None, None]:
    """分块读取文件内容，支持大型日志文件。

    Args:
        path: 文件路径。
        chunk_size: 每次读取的块大小（字节）。

    Yields:
        文件内容块。
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            yield data


def iter_lines(path: str) -> Iterable[str]:
    """惰性行迭代器，用于流式处理。

    Args:
        path: 文件路径。

    Yields:
        文件的每一行。
    """
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            yield line


# ==================== 智能读取 ====================


def read_text_limited(path: str, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
    """智能加载文件：大文件只读取头部和尾部。

    策略：
    1. 如果文件大小 < max_bytes：全量加载。
    2. 如果文件大小 > max_bytes：加载前 50% 和后 50%。
       中间插入 '...[TRUNCATED]...' 标记。

    Args:
        path: 文件路径。
        max_bytes: 最大读取字节数。

    Returns:
        文件内容字符串。

    Raises:
        ValueError: If file exceeds MAX_FILE_SIZE_HARD_LIMIT (V-008 DoS protection).
    """
    # V-008 Fix: Enforce hard size limit before any reading to prevent DoS
    size = os.path.getsize(path)

    if size > MAX_FILE_SIZE_HARD_LIMIT:
        raise ValueError(
            f"文件超过硬性大小上限 ({size} bytes > {MAX_FILE_SIZE_HARD_LIMIT} bytes): {path}"
        )

    try:
        if size <= max_bytes:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        # 大文件策略：读取头尾
        half = max_bytes // 2
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            head = f.read(half)

            # 定位到尾部
            f.seek(max(0, size - half), os.SEEK_SET)
            tail = f.read()

            return (
                f"{head}\n\n"
                f"...[FILE TRUNCATED {size} bytes -> "
                f"{len(head) + len(tail)} bytes detected]...\n\n"
                f"{tail}"
            )
    except Exception as e:
        # 回退到简单读取
        import logging
        logging.getLogger(__name__).warning(f"智能读取失败，回退到简单读取: {e}")
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_bytes)


def read_text_head(path: str, max_bytes: int = DEFAULT_MAX_BYTES) -> str:
    """快速读取文件头部内容。

    适合只需崩溃上下文的场景，避免尾部 seek。

    Args:
        path: 文件路径。
        max_bytes: 最大读取字节数。

    Returns:
        文件头部内容，失败时返回空字符串。
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_bytes)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"读取文件头部失败: {e}")
        return ""


# ==================== 安全读写 ====================


def read_with_backup(
    file_path: str, encoding: str = "utf-8", backup_count: int = 3
) -> str | None:
    """带备份回退的文件读取。

    如果主文件读取失败，尝试读取备份文件。

    Args:
        file_path: 文件路径。
        encoding: 文件编码。
        backup_count: 备份文件数量。

    Returns:
        文件内容，全部失败返回 None。
    """
    try:
        with open(file_path, "r", encoding=encoding) as f:
            return f.read()
    except Exception:
        for i in range(1, backup_count + 1):
            bak = f"{file_path}.bak{i}"
            if os.path.exists(bak):
                try:
                    with open(bak, "r", encoding=encoding) as f:
                        return f.read()
                except Exception:
                    continue
    return None


def write_atomic(
    file_path: str, content: str, encoding: str = "utf-8"
) -> None:
    """原子写入文件。

    先写入临时文件，然后移动到目标位置，避免写入中断导致数据丢失。

    Args:
        file_path: 目标文件路径。
        content: 要写入的内容。
        encoding: 文件编码。
    """
    tmp_path = file_path + ".tmp"
    with open(tmp_path, "w", encoding=encoding) as f:
        f.write(content)
    shutil.move(tmp_path, file_path)


# ==================== 便捷类 ====================


class SafeFileOperator:
    """安全文件操作器（向后兼容的静态方法封装）。"""

    @staticmethod
    def read_with_backup(
        file_path: str, encoding: str = "utf-8", backup_count: int = 3
    ) -> str | None:
        """带备份回退的文件读取。"""
        return read_with_backup(file_path, encoding, backup_count)

    @staticmethod
    def write_atomic(
        file_path: str, content: str, encoding: str = "utf-8"
    ) -> None:
        """原子写入文件。"""
        write_atomic(file_path, content, encoding)
