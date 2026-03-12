from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Optional, Union

@dataclass
class AnalysisChunk:
    content: str
    offset: int


class StreamingLogAnalyzer:
    def __init__(self, file_path: str, chunk_size: int = 8192):
        self.file_path = file_path
        self.chunk_size = chunk_size

    def analyze_incremental(self, callback: Callable[[AnalysisChunk], Union[bool, None]]):
        offset = 0
        with open(self.file_path, "r", encoding="utf-8", errors="ignore") as f:
            while True:
                data = f.read(self.chunk_size)
                if not data:
                    break
                result = callback(AnalysisChunk(content=data, offset=offset))
                offset += len(data)
                if result is False:
                    break
