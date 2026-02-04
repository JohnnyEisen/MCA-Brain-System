from __future__ import annotations
import os
import shutil
from typing import Optional


class SafeFileOperator:
    @staticmethod
    def read_with_backup(file_path: str, encoding: str = "utf-8", backup_count: int = 3) -> Optional[str]:
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

    @staticmethod
    def write_atomic(file_path: str, content: str, encoding: str = "utf-8") -> None:
        tmp_path = file_path + ".tmp"
        with open(tmp_path, "w", encoding=encoding) as f:
            f.write(content)
        shutil.move(tmp_path, file_path)
