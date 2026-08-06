"""Traditional RAG facade: dense+sparse fuse (Qdrant RRF) -> hydrate Postgres -> rerank.

Đây là một trong hai mode (traditional/hybrid). Dùng standalone cho debug/eval/
ablation. `graph_context` luôn rỗng ở mode này (đó là phần của GraphRAG). Sau cải tiến:
dense (semantic) + BM25 (keyword) fuse RRF SERVER-SIDE trong Qdrant rồi rerank cross-encoder
(no-op nếu `RERANKER_MODEL` rỗng). Backend lỗi -> RetrievalBackendError propagate.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.reranker import rerank
from app.schemas.retrieval import RetrievalResult, RetrievedChunk
from app.tools.graph_rag.chunk_store import get_rag_chunks_by_ids
from app.tools.graph_rag.vector_store import search_dense_sparse

__all__ = ["retrieve_traditional"]


async def retrieve_traditional(
    question: str,
    *,
    top_k: int | None = None,
    bm25_top_k: int | None = None,
    rerank_top_k: int | None = None,
) -> RetrievalResult:
    """Dense+sparse fuse -> hydrate Postgres (một lần) -> rerank + cắt `rerank_top_k`.

    Các kwarg None -> fallback settings (Cấu hình hệ thống truyền giá trị admin vào).
    """
    candidates = await search_dense_sparse(question, top_k=top_k, bm25_top_k=bm25_top_k)
    if not candidates:
        return RetrievalResult(mode="traditional", query=question, chunks=[])

    chunk_ids = [c.chunk_id for c in candidates]
    rows = await asyncio.to_thread(get_rag_chunks_by_ids, chunk_ids)
    by_id = {row["chunk_id"]: row for row in rows}

    chunks: list[RetrievedChunk] = []
    warnings: list[str] = []
    for cand in candidates:  # giữ thứ tự fused rank trước khi rerank
        row = by_id.get(cand.chunk_id)
        if row is None:
            warnings.append(f"chunk thiếu trong Postgres: {cand.chunk_id}")
            continue
        chunks.append(
            RetrievedChunk(
                chunk_id=row["chunk_id"],
                text=row["text"],
                metadata=row.get("metadata") or {},
                heading_path=row.get("heading_path") or [],
                vector_score=cand.score,  # = điểm RRF fused (dense+sparse)
                sources=["vector"],
            )
        )

    chunks = await rerank(question, chunks)
    cut = rerank_top_k if rerank_top_k is not None else get_settings().rerank_top_k
    chunks = chunks[:cut]
    return RetrievalResult(
        mode="traditional", query=question, chunks=chunks, warnings=warnings
    )
