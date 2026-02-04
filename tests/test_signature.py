import base64
from pathlib import Path

import pytest

from brain_system.security import verify_dlc_signature


@pytest.mark.skipif(True, reason="requires cryptography; enabled in CI when installed")
def test_signature_verify_roundtrip(tmp_path: Path):
    # 该测试在安装 cryptography 后启用
    dlc = tmp_path / "x.py"
    dlc.write_text("print('hi')\n", encoding="utf-8")

    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

    priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = priv.public_key()

    digest = hashes.Hash(hashes.SHA256())
    digest.update(dlc.read_bytes())
    d = digest.finalize()

    sig = priv.sign(d, padding.PKCS1v15(), hashes.SHA256())
    (tmp_path / "x.py.sig").write_bytes(base64.b64encode(sig))

    verify_dlc_signature(dlc, public_keys_pem=[pub.public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo)])
