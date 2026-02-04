from __future__ import annotations

from typing import Any, Optional


def create_app(brain: Any):
    """创建 HTTP 服务：health/ready/metrics。

    依赖：FastAPI + (可选) prometheus_client。
    """

    try:
        from fastapi import FastAPI
        from fastapi.responses import PlainTextResponse
    except Exception as e:  # pragma: no cover
        raise RuntimeError("未安装 server 依赖，安装: pip install 'brain-system[server]'") from e

    app = FastAPI(title="brain-system")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ready")
    def ready():
        # 简化：只要 BrainCore 初始化完成即可
        return {"ready": True, "dlcs": len(getattr(brain, "dlcs", {}))}

    @app.get("/metrics")
    def metrics():
        try:
            from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

            data = generate_latest()
            return PlainTextResponse(content=data.decode("utf-8"), media_type=CONTENT_TYPE_LATEST)
        except Exception:
            return PlainTextResponse(content="# metrics disabled\n", media_type="text/plain")

    return app
