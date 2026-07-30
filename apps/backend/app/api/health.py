"""Health/readiness probes.

- `/health`: process còn sống (luôn 200). Dùng cho liveness probe.
- `/ready`: config bắt buộc + kết nối được Postgres. Ping agent-service là OPTIONAL
  (chỉ báo cáo, không làm /ready fail) vì backend vẫn phục vụ auth/conversation khi
  agent tạm sập. Thiếu config/Postgres -> 503.
"""

from __future__ import annotations

import anyio
import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.db import check_connection

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


async def _ping_agent(url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{url.rstrip('/')}/ready")
            return resp.status_code == 200
    except Exception:
        return False


@router.get("/ready")
async def ready() -> JSONResponse:
    settings = get_settings()
    db_ok = await anyio.to_thread.run_sync(check_connection)
    checks = {
        "secret_key": settings.backend_secret_key != "change-me-to-a-long-random-string",
        # Thiếu key này thì MỌI request nội bộ 2 chiều bị từ chối (fail-closed) -> /ask chết.
        # Đưa vào ready để lộ ngay lúc deploy, không đợi câu hỏi đầu tiên của user.
        "internal_api_key": bool(settings.internal_api_key),
        "database_url": bool(settings.database_url),
        "postgres": db_ok,
        "agent_service": await _ping_agent(settings.agent_service_url),  # informational
    }
    # agent_service không tính vào điều kiện ready (optional theo plan).
    required_ok = (
        checks["database_url"] and checks["postgres"] and checks["internal_api_key"]
    )
    status_code = 200 if required_ok else 503
    return JSONResponse(
        status_code=status_code,
        content={"status": "ready" if required_ok else "not_ready", "checks": checks},
    )
