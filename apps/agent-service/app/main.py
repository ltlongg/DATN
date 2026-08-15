"""Entrypoint FastAPI cho agent-service. Chạy: `uvicorn app.main:app --port 9000`."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI

from app.api.ask import router as ask_router
from app.api.health import router as health_router
from app.api.kb import router as kb_router
from app.core.embedding import embed_texts
from app.core.internal_auth import verify_internal_key
from app.core.postgres import close_pool, get_pool
from app.core.reranker import rerank
from app.core.sparse import encode_query
from app.schemas.retrieval import RetrievedChunk

# import app.core.config (qua app.api.ask -> ...) đã set HF_HUB_DISABLE_SYMLINKS=1 —
# xem app/core/config.py.

logger = logging.getLogger("agent_service.startup")

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Warm-up model nặng (dense embedding + BM25 sparse + cross-encoder rerank) TRƯỚC khi
    nhận request thật.

    Cả ba model lazy-load lần gọi đầu (embedding: vài chục giây; sparse: có thể kèm tải
    HuggingFace; reranker: ~4s nạp weight lên GPU). Không warm-up -> câu hỏi đầu tiên của
    user ăn trọn latency đó bên trong node `retrieve`, dễ vượt idle-read timeout 30s phía
    backend -> lỗi "Luồng trả lời bị gián đoạn" dù agent-service vẫn đang chạy bình thường.
    `rerank` tự no-op khi RERANKER_MODEL rỗng nên warm-up này miễn phí lúc reranker tắt.
    Lỗi warm-up không chặn startup — model sẽ lazy-load lại ở request đầu như hành vi cũ.

    Đo thực tế (RTX 4060, 2026-07-14): warm-up này kéo node `retrieve` của request ĐẦU về
    ~0.9s (ngang request sau). Cold còn lại của request đầu (~5s) nằm ở `plan` — là
    handshake HTTP/TLS lần đầu tới gateway LLM, KHÔNG phải model, warm ở đây không chữa
    được."""
    try:
        await embed_texts(["warm-up"])
        await asyncio.to_thread(encode_query, "warm-up")
        await rerank(
            "warm-up",
            [RetrievedChunk(chunk_id="warm-up", text="warm-up", metadata={}, heading_path=[])],
        )
        logger.info("model warm-up xong (embedding + sparse + reranker)")
    except Exception:
        logger.exception("model warm-up lỗi — sẽ lazy-load lại ở request đầu")
    try:
        get_pool()  # mở pool Postgres sẵn; lỗi không chặn startup (pool tự lấp lại)
    except Exception:
        logger.exception("mở pool Postgres lỗi — sẽ thử lại ở request đầu")
    yield
    close_pool()

def create_app() -> FastAPI:
    app = FastAPI(title="Agent Service", version="0.1.0", lifespan=lifespan)
    # Gác `X-Internal-Key` ở CẤP ROUTER (không phải cấp app) để `health_router` ở dưới còn
    # public cho probe. Route thêm sau vào 2 router này tự động được gác — xem internal_auth.py.
    guarded = [Depends(verify_internal_key)]
    app.include_router(ask_router, dependencies=guarded)
    app.include_router(kb_router, dependencies=guarded)
    app.include_router(health_router)
    return app

app = create_app()
