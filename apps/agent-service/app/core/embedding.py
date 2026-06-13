"""Sinh embedding tiếng Việt (vector thật) bằng sentence-transformers.

Khác với `app/indexing/token_counter.py` (chỉ dùng tokenizer để ĐẾM token cho ngưỡng
chunk), module này nạp cả model để SINH vector embedding — dùng cho vector indexing
(Qdrant) và retrieval. Model `AITeamVN/Vietnamese_Embedding` (nền BGE-M3) cho chất
lượng tiếng Việt tốt hơn embedding OpenAI.

Cung cấp hàm `embed_texts()` **async** bằng cách chạy `model.encode()` (đồng bộ, nặng
CPU/GPU) trong thread riêng qua `asyncio.to_thread` để không chẹn event loop (CLI sync
gọi qua `asyncio.run`). Model lazy-load + cache module-level — lần gọi đầu tốn vài chục
giây.
"""

from __future__ import annotations

import asyncio
from threading import Lock

import numpy as np

from app.core.config import get_settings

_model = None  # cache SentenceTransformer (nạp 1 lần)
_model_lock = Lock()

EMBEDDING_DIM = 1024  # AITeamVN/Vietnamese_Embedding (BGE-M3 base)
EMBEDDING_MAX_TOKENS = 2048  # model card: fine-tune tại 2048, ép về đây từ default 8192


def _get_model():
    """Lazy-load SentenceTransformer, cache lại cho các lần sau."""
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                # import trong hàm: tránh kéo torch nặng khi chỉ import module này để lấy hằng số.
                from sentence_transformers import SentenceTransformer

                _model = SentenceTransformer(get_settings().embedding_model)
                _model.max_seq_length = EMBEDDING_MAX_TOKENS
    return _model


def _encode(texts: list[str]) -> np.ndarray:
    # normalize_embeddings=True: vector chuẩn hóa L2 -> cosine = dot product, hợp với
    # vector store. convert_to_numpy: trả np.ndarray (n, dim).
    return _get_model().encode(
        texts, normalize_embeddings=True, convert_to_numpy=True
    )


async def embed_texts(texts: list[str]) -> np.ndarray:
    """Sinh embedding cho list văn bản (async, an toàn cho event loop)."""
    if not texts:
        return np.empty((0, EMBEDDING_DIM), dtype=np.float32)
    return await asyncio.to_thread(_encode, list(texts))
