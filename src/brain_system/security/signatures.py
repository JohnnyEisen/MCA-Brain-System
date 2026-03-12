from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


class SignatureVerificationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class DlcSignatureConfig:
    required: bool
    public_key_pem_files: tuple[str, ...] = ()


def _sha256_file(path: Path) -> bytes:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.digest()


def _load_sig(path: Path) -> bytes:
    sig_path = Path(str(path) + ".sig")
    if not sig_path.exists():
        raise SignatureVerificationError(f"缺少签名文件: {sig_path}")
    raw = sig_path.read_bytes().strip()
    try:
        return base64.b64decode(raw, validate=True)
    except Exception as e:  # noqa: BLE001
        raise SignatureVerificationError(f"签名文件不是有效 base64: {sig_path}") from e


def verify_dlc_signature(
    dlc_path: Path,
    *,
    public_keys_pem: Iterable[bytes],
) -> None:
    """验证 DLC 文件签名。

    约定：
    - `xxx.py.sig` 存在且为 base64
    - 签名内容为 `SHA256(xxx.py)` 的 digest

    支持 RSA/ECDSA 公钥（cryptography）。
    """

    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
    except Exception as e:  # pragma: no cover
        raise SignatureVerificationError(
            "未安装 cryptography，无法进行 DLC 签名验证。安装: pip install 'brain-system[crypto]'"
        ) from e

    digest = _sha256_file(dlc_path)
    signature = _load_sig(dlc_path)

    last_error: Optional[Exception] = None
    for pem in public_keys_pem:
        try:
            key = load_pem_public_key(pem)
            if isinstance(key, rsa.RSAPublicKey):
                key.verify(signature, digest, padding.PKCS1v15(), hashes.SHA256())
                return
            if isinstance(key, ec.EllipticCurvePublicKey):
                key.verify(signature, digest, ec.ECDSA(hashes.SHA256()))
                return
            last_error = SignatureVerificationError("不支持的公钥类型")
        except Exception as e:  # noqa: BLE001
            last_error = e
            continue

    raise SignatureVerificationError(f"DLC 签名验证失败: {dlc_path} ({last_error})")


def load_public_keys_from_files(paths: Iterable[str]) -> list[bytes]:
    out: list[bytes] = []
    for p in paths:
        b = Path(p).expanduser().read_bytes()
        out.append(b)
    return out
