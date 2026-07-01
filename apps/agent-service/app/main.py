"""Entrypoint FastAPI cho agent-service. Chạy: `uvicorn app.main:app --port 9000`."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.ask import router as ask_router
from app.api.kb import router as kb_router


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Service", version="0.1.0")
    app.include_router(ask_router)
    app.include_router(kb_router)
    return app


app = create_app()
