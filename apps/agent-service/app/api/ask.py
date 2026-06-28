"""Router /ask + /health + /ready. `/ask` là internal endpoint cho backend gọi.

stream=True -> SSE (lỗi sau khi mở đi qua event `error`). stream=False -> 1 AskResponse
JSON, lỗi dependency/timeout map về HTTP status sạch (422/503/504/500).
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import get_settings
from app.orchestrator.errors import SynthesisError
from app.orchestrator.runner import error_code, error_message, run_ask, run_ask_stream
from app.schemas.ask import AskRequest, AskResponse
from app.schemas.retrieval import RetrievalBackendError

router = APIRouter()


@router.post("/ask", response_model=AskResponse)
async def ask(request: AskRequest):  # type: ignore[no-untyped-def]
    if request.stream:
        # Một khi return StreamingResponse là HTTP 200 + byte đầu đã gửi -> lỗi sau đó
        # KHÔNG đổi được status, đi qua event `error` bên trong run_ask_stream.
        return StreamingResponse(
            run_ask_stream(request),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    settings = get_settings()
    try:
        return await asyncio.wait_for(run_ask(request), timeout=settings.ask_timeout_seconds)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504, detail={"code": "timeout", "message": "Quá thời gian xử lý câu hỏi."}
        )
    except (RetrievalBackendError, SynthesisError) as exc:
        raise HTTPException(
            status_code=503, detail={"code": error_code(exc), "message": error_message(exc)}
        )


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
    }
    if not all(checks.values()):
        raise HTTPException(status_code=503, detail={"code": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}
