"""security: 安全序列化与校验模块。"""
from __future__ import annotations

import base64
import hashlib
import json
import pickle
import logging
from pathlib import Path
from typing import Any, Union

# Export signature utilities to be backward compatible and useful
from .signatures import (
    SignatureVerificationError,
    DlcSignatureConfig,
    verify_dlc_signature,
    load_public_keys_from_files
)

class SafeSerializer:
    """安全序列化器：优先使用 JSON，受限使用 pickle。"""

    @staticmethod
    def serialize(data: Any, format: str = "json") -> bytes:
        if format == "json":
            return json.dumps(data).encode("utf-8")
        elif format == "pickle":
            # 注意：Pickle 不安全，仅用于受信任内部数据
            return pickle.dumps(data)
        elif format == "base64_pickle":
            return base64.b64encode(pickle.dumps(data))
        else:
            raise ValueError(f"不支持的序列化格式: {format}")

    @staticmethod
    def deserialize(data: bytes, format: str = "json") -> Any:
        if format == "json":
            return json.loads(data.decode("utf-8"))
        elif format == "pickle":
            return pickle.loads(data)
        elif format == "base64_pickle":
            return pickle.loads(base64.b64decode(data))
        else:
            raise ValueError(f"不支持的反序列化格式: {format}")

    @staticmethod
    def validate_file_signature(path: Union[str, Path], public_keys_pem: list[bytes]) -> bool:
        """校验文件签名，防止被篡改。委托给 verify_dlc_signature。"""
        try:
            verify_dlc_signature(Path(path), public_keys_pem=public_keys_pem)
            return True
        except SignatureVerificationError:
            return False
        except Exception:
            return False
