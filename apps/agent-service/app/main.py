"""Entrypoint FastAPI cho agent-service. Chạy: `uvicorn app.main:app --port 9000`."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.ask import router as ask_router
from app.api.kb import router as kb_router
from app.core.embedding import embed_texts
from app.core.sparse import encode_query

# import app.core.config (qua app.api.ask -> ...) đã set HF_HUB_DISABLE_SYMLINKS=1 —
# xem app/core/config.py.

logger = logging.getLogger("agent_service.startup")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Warm-up model nặng (dense embedding + BM25 sparse) TRƯỚC khi nhận request thật.

    Cả hai model lazy-load lần gọi đầu (embedding: vài chục giây; sparse: có thể kèm tải
    HuggingFace). Không warm-up -> câu hỏi đầu tiên của user ăn trọn latency đó bên trong
    node `retrieve`, dễ vượt idle-read timeout 30s phía backend -> lỗi "Luồng trả lời bị
    gián đoạn" dù agent-service vẫn đang chạy bình thường. Lỗi warm-up không chặn startup —
    model sẽ lazy-load lại ở request đầu như hành vi cũ."""
    try:
        await embed_texts(["warm-up"])
        await asyncio.to_thread(encode_query, "warm-up")
        logger.info("model warm-up xong (embedding + sparse)")
    except Exception:
        logger.exception("model warm-up lỗi — sẽ lazy-load lại ở request đầu")
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Agent Service", version="0.1.0", lifespan=lifespan)
    app.include_router(ask_router)
    app.include_router(kb_router)
    return app


app = create_app()
