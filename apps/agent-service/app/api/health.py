"""Probe liveness/readiness — router PUBLIC, cố ý KHÔNG gác `X-Internal-Key`.

Tách khỏi `api/ask.py` khi thêm auth nội bộ (xem app/core/internal_auth.py): gác cả router
`ask` thì 2 probe này cũng bị gác, mà backend `api/health.py::_ping_agent` gọi `GET /ready`
KHÔNG mang header -> `/ready` của backend sẽ báo `agent_service: false` vĩnh viễn, nhìn như
agent sập. Probe vốn nên public: nó chỉ trả cờ boolean "config có mặt hay không", không trả
giá trị config nào.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.core.config import get_settings

router = APIRouter(tags=["health"])

@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}

@router.get("/ready")
async def ready() -> dict[str, object]:
    settings = get_settings()
    checks = {
        "openai_api_key": bool(settings.openai_api_key),
        "database_url": bool(settings.database_url),
        "qdrant_host": bool(settings.qdrant_host),
        "neo4j_uri": bool(settings.neo4j_uri),
        # Thiếu key này thì backend gọi /ask sẽ nhận 500 -> đưa vào điều kiện ready để phát
        # hiện lúc deploy, thay vì đợi câu hỏi đầu tiên của user mới lộ.
        "internal_api_key": bool(settings.internal_api_key),
    }
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail={"code": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}
