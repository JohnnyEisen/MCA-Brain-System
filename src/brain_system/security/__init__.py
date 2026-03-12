"""security: 安全序列化与校验模块。

V-011 Fix: 移除不安全的pickle反序列化，改用JSON+签名验证
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import struct
from pathlib import Path
from typing import Any, Union

# Export signature utilities to be backward compatible and useful
from .signatures import (
    SignatureVerificationError,
    DlcSignatureConfig,
    verify_dlc_signature,
    load_public_keys_from_files
)

_logger = logging.getLogger(__name__)

_SERIALIZATION_SECRET: bytes = b""
_SERIALIZATION_SECRET_SET = False

def set_serialization_secret(secret: bytes) -> None:
    """设置序列化签名密钥（启动时调用一次）"""
    global _SERIALIZATION_SECRET, _SERIALIZATION_SECRET_SET
    _SERIALIZATION_SECRET = secret
    _SERIALIZATION_SECRET_SET = True

def _get_serialization_secret() -> bytes:
    """获取序列化签名密钥"""
    global _SERIALIZATION_SECRET
    if not _SERIALIZATION_SECRET_SET:
        _SERIALIZATION_SECRET = os.environ.get("MCA_SERIAL_SECRET", "default-dev-key-change-in-prod").encode()
    return _SERIALIZATION_SECRET

class UnsafeDeserializationError(RuntimeError):
    """当检测到不安全的数据时抛出"""
    pass

class SafeSerializer:
    """安全序列化器：使用JSON+HMAC签名，完全移除pickle。

    V-011 Fix: 
    - 移除pickle反序列化（RCE风险）
    - 使用JSON作为唯一序列化格式
    - 添加HMAC签名验证防止篡改
    - 支持numpy数组的JSON序列化
    """

    MAGIC_HEADER = b"MCAJSON1"
    VERSION = 1

    @staticmethod
    def _numpy_to_json(obj: Any) -> Any:
        """将numpy数组转换为JSON可序列化格式"""
        try:
            import numpy as np
            if isinstance(obj, np.ndarray):
                return {"__ndarray__": True, "data": obj.tolist(), "dtype": str(obj.dtype)}
            if isinstance(obj, (np.integer, np.floating)):
                return obj.item()
            if isinstance(obj, np.bool_):
                return bool(obj)
        except ImportError:
            pass
        return obj

    @staticmethod
    def _json_to_numpy(obj: Any) -> Any:
        """从JSON还原numpy数组"""
        if isinstance(obj, dict) and obj.get("__ndarray__"):
            try:
                import numpy as np
                return np.array(obj["data"], dtype=obj["dtype"])
            except ImportError:
                return obj["data"]
        return obj

    @classmethod
    def serialize(cls, data: Any, format: str = "json") -> bytes:
        """序列化数据为带签名的JSON格式。

        Args:
            data: 要序列化的数据
            format: 序列化格式（仅支持json）

        Returns:
            带签名头的序列化数据

        Raises:
            ValueError: 不支持的格式
        """
        if format not in ("json", "pickle", "base64_pickle"):
            raise ValueError(f"不支持的序列化格式: {format}")

        if format in ("pickle", "base64_pickle"):
            _logger.warning(
                "pickle格式已被弃用且不安全，自动切换到json格式。"
                "请更新代码使用json格式。"
            )
            format = "json"

        def _convert(obj: Any) -> Any:
            if isinstance(obj, dict):
                return {k: _convert(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [_convert(item) for item in obj]
            else:
                return cls._numpy_to_json(obj)

        json_data = json.dumps(_convert(data), ensure_ascii=False, default=str)
        json_bytes = json_data.encode("utf-8")

        secret = _get_serialization_secret()
        signature = hmac.new(secret, json_bytes, hashlib.sha256).digest()

        header = cls.MAGIC_HEADER + struct.pack(">I", cls.VERSION) + struct.pack(">I", len(signature))
        return header + signature + json_bytes

    @classmethod
    def deserialize(cls, data: bytes, format: str = "json") -> Any:
        """反序列化带签名的JSON数据。

        Args:
            data: 带签名的序列化数据
            format: 序列化格式（仅支持json）

        Returns:
            反序列化的数据

        Raises:
            UnsafeDeserializationError: 签名验证失败或数据被篡改
            ValueError: 不支持的格式或数据格式错误
        """
        if format not in ("json", "pickle", "base64_pickle"):
            raise ValueError(f"不支持的反序列化格式: {format}")

        if format in ("pickle", "base64_pickle"):
            _logger.warning(
                "pickle格式已被弃用且不安全，自动切换到json格式。"
                "如果数据是pickle格式，将拒绝反序列化。"
            )
            format = "json"

        if len(data) < len(cls.MAGIC_HEADER) + 8:
            raise UnsafeDeserializationError("数据格式无效：数据太短")

        header = data[:len(cls.MAGIC_HEADER)]
        if header != cls.MAGIC_HEADER:
            raise UnsafeDeserializationError(
                "数据格式无效：缺少安全头。"
                "旧格式数据不再支持，请使用新格式重新保存。"
            )

        offset = len(cls.MAGIC_HEADER)
        version = struct.unpack(">I", data[offset:offset+4])[0]
        offset += 4

        if version != cls.VERSION:
            raise UnsafeDeserializationError(f"不支持的版本: {version}")

        sig_len = struct.unpack(">I", data[offset:offset+4])[0]
        offset += 4

        stored_signature = data[offset:offset+sig_len]
        offset += sig_len

        json_bytes = data[offset:]

        secret = _get_serialization_secret()
        expected_signature = hmac.new(secret, json_bytes, hashlib.sha256).digest()

        if not hmac.compare_digest(stored_signature, expected_signature):
            raise UnsafeDeserializationError(
                "签名验证失败：数据可能被篡改或密钥不匹配"
            )

        json_data = json.loads(json_bytes.decode("utf-8"))

        def _convert(obj: Any) -> Any:
            if isinstance(obj, dict):
                converted = cls._json_to_numpy(obj)
                if converted is not obj:
                    return converted
                return {k: _convert(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [_convert(item) for item in obj]
            else:
                return obj

        return _convert(json_data)

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
