运维手册
========

启动方式
--------

- 本地：`brain serve --host 0.0.0.0 --port 8000`
- 健康检查：`GET /health`
- 就绪检查：`GET /ready`
- 指标：`GET /metrics`

安全
----

DLC 动态加载默认支持签名验证：

- `dlc_signature_required=true`：强制所有 DLC 必须存在 `.sig` 且验签通过
- `dlc_signature_verify_if_present=true`：如果存在 `.sig` 则验签
- `dlc_public_key_pem_files=["path/to/pub.pem"]`：配置公钥

