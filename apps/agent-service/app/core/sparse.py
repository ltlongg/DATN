"""Sparse BM25 encoder (fastembed) cho keyword retrieval.

Chọn fastembed client-side thay vì server-side inference của Qdrant: **deterministic +
mock được trong unit test**, không phụ thuộc tính năng inference của server. Model
`Qdrant/bm25` cố ý BỎ IDF (để Qdrant tự tính qua `Modifier.IDF` ở collection) — vì vậy
phải bật modifier đó khi tạo collection (xem `core/qdrant.py`).

Lazy-load + cache model (pattern giống `core/reranker.py`); forward chạy CPU nên caller bọc
`asyncio.to_thread` ở context async. `embed()` = encode document (có TF), `query_embed()` =
encode query. Trả `(indices, values)` đã `tolist()` để đẩy thẳng vào `SparseVector` của Qdrant.
"""

from __future__ import annotations

from threading import Lock

from app.core.config import get_settings

__all__ = ["encode_documents", "encode_query"]

_model: dict[str, object] = {}
_lock = Lock()


def _get():
    """Lazy-load + cache SparseTextEmbedding theo bm25_model trong config."""
    cached = _model.get("m")
    if cached is None:
        with _lock:
            cached = _model.get("m")
            if cached is None:
                from fastembed import SparseTextEmbedding

                cached = SparseTextEmbedding(get_settings().bm25_model)
                _model["m"] = cached
    return cached


def encode_documents(texts: list[str]) -> list[tuple[list[int], list[float]]]:
    """Encode nhiều document -> [(indices, values), ...] cùng thứ tự `texts`."""
    embeddings = _get().embed(texts)  # type: ignore[attr-defined]
    return [(e.indices.tolist(), e.values.tolist()) for e in embeddings]


def encode_query(text: str) -> tuple[list[int], list[float]]:
    """Encode 1 query -> (indices, values). query_embed khác embed (không TF weighting)."""
    embedding = next(iter(_get().query_embed(text)))  # type: ignore[attr-defined]
    return embedding.indices.tolist(), embedding.values.tolist()
