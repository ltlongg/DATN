"""FastAPI app cho backend API gateway.

Lắp CORS, error handler chuẩn hóa, middleware gắn `X-Request-ID` (debug/observability),
và mount các router. Backend KHÔNG tự làm RAG/LLM — chỉ auth + conversation + proxy
streaming sang agent-service (xem docs/plan/backend-plan.md).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

import anyio
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api import (
    activity,
    auth,
    chat,
    config,
    cost,
    documents,
    health,
    inspect,
    internal,
    logs,
    prompts,
    users,
)
from app.core.config import get_settings
from app.core.db import close_pool, get_pool
from app.core.errors import register_error_handlers
from app.core.security import TokenError, decode_access_token
from app.models.activity import record_activity

logger = logging.getLogger("backend.startup")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Mở pool Postgres lúc startup (warm sẵn connection) và đóng sạch lúc shutdown.
    Lỗi mở pool KHÔNG chặn startup — pool tự lấp connection lại ở request đầu."""
    try:
        get_pool()
    except Exception:
        logger.exception("Mở pool Postgres lỗi — sẽ thử lại ở request đầu")
    yield
    close_pool()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Gắn X-Request-ID cho mỗi request (nhận từ client hoặc sinh mới) để trace log."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


def _should_log_activity(request: Request) -> bool:
    """Chỉ log request /api/* có ý nghĩa: bỏ CORS preflight, non-API (health/static), và
    chính feed activity (tránh admin refresh tự làm ngập log)."""
    if request.method == "OPTIONS":
        return False
    path = request.url.path
    return path.startswith("/api/") and not path.startswith("/api/admin/activity")


def _user_id_from_request(request: Request) -> str | None:
    """Best-effort lấy user_id từ Bearer token (KHÔNG đụng deps.py — request chưa auth vẫn
    log được với user NULL). Token thiếu/không hợp lệ -> None."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return None
    try:
        payload = decode_access_token(header.removeprefix("Bearer "))
    except TokenError:
        return None
    sub = payload.get("sub")
    return str(sub) if sub is not None else None


class ActivityLogMiddleware(BaseHTTPMiddleware):
    """Ghi 1 dòng activity_log cho mỗi request /api/*. Phải chạy TRONG RequestIDMiddleware
    (thêm TRƯỚC nó ở create_app) để đọc được request.state.request_id. Xem activity-log-plan.md."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if not _should_log_activity(request):
            return await call_next(request)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:  # lỗi CHƯA được handler bắt (vd ProgrammingError 500 thô)
            await self._record(request, 500, start, f"{type(exc).__name__}: {str(exc)[:200]}")
            raise  # re-raise để ServerErrorMiddleware xử lý như cũ
        error = None
        if response.status_code >= 400:
            # Lỗi đã handled: handler ghi code lên request.state (core/errors.py). Fallback
            # phòng khi status >= 400 đến từ nơi không set (vd Response thô của framework).
            error = getattr(request.state, "error_code", None) or f"HTTP {response.status_code}"
        await self._record(request, response.status_code, start, error)
        return response

    @staticmethod
    async def _record(
        request: Request, status_code: int, start: float, error: str | None
    ) -> None:
        await anyio.to_thread.run_sync(
            partial(
                record_activity,
                request_id=getattr(request.state, "request_id", None),
                user_id=_user_id_from_request(request),
                method=request.method,
                path=request.url.path,
                status_code=status_code,
                severity="error" if status_code >= 400 else "ok",
                latency_ms=round((time.perf_counter() - start) * 1000),
                error=error,
            )
        )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Agentic RAG Backend", version="0.1.0", lifespan=lifespan)

    # Thứ tự QUAN TRỌNG: Starlette chạy middleware thêm-sau = bọc-ngoài = chạy-trước. Thêm
    # ActivityLog TRƯỚC RequestID -> ActivityLog nằm TRONG -> chạy SAU khi RequestID đã set
    # request.state.request_id. CORS thêm cuối -> ngoài cùng.
    app.add_middleware(ActivityLogMiddleware)
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_error_handlers(app)

    app.include_router(health.router)
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(documents.router, prefix="/api/admin/documents", tags=["documents"])
    app.include_router(inspect.router, prefix="/api/admin/kb", tags=["kb-inspect"])
    app.include_router(logs.router, prefix="/api/admin/logs", tags=["admin-logs"])
    app.include_router(users.router, prefix="/api/admin/users", tags=["admin-users"])
    app.include_router(cost.router, prefix="/api/admin/cost", tags=["admin-cost"])
    app.include_router(prompts.router, prefix="/api/admin/prompts", tags=["admin-prompts"])
    app.include_router(activity.router, prefix="/api/admin/activity", tags=["admin-activity"])
    app.include_router(config.router, prefix="/api/admin/config", tags=["admin-config"])
    # Nội bộ (agent-service gọi) — KHÔNG /api/admin, KHÔNG auth. Xem api/internal.py.
    app.include_router(internal.router, prefix="/internal", tags=["internal"])

    return app


app = create_app()
