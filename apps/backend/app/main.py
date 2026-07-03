"""FastAPI app cho backend API gateway.

Lắp CORS, error handler chuẩn hóa, middleware gắn `X-Request-ID` (debug/observability),
và mount các router. Backend KHÔNG tự làm RAG/LLM — chỉ auth + conversation + proxy
streaming sang agent-service (xem docs/plan/backend-plan.md).
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from app.api import auth, chat, cost, documents, health, inspect, logs, users
from app.core.config import get_settings
from app.core.db import close_pool, get_pool
from app.core.errors import register_error_handlers

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


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Agentic RAG Backend", version="0.1.0", lifespan=lifespan)

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

    return app


app = create_app()
