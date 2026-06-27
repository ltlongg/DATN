"""Traditional RAG facade: vector search -> hydrate Postgres -> RetrievalResult.

Đây là một trong ba mode (traditional/graph/hybrid). Dùng standalone cho debug/eval/
ablation; runtime mặc định đi hybrid. `graph_context` luôn rỗng ở mode này (đó là phần
của GraphRAG). Backend lỗi -> RetrievalBackendError propagate từ `search_vector`.
"""

from __future__ import annotations

import asyncio

from app.tools.graph_rag.chunk_store import get_rag_chunks_by_ids
from app.tools.graph_rag.vector_store import search_vector
from app.schemas.retrieval import RetrievalResult, RetrievedChunk

__all__ = ["retrieve_traditional"]


async def retrieve_traditional(
    question: str, *, top_k: int | None = None
) -> RetrievalResult:
    """Embed + Qdrant search rồi hydrate full text/metadata từ Postgres (một lần)."""
    candidates = await search_vector(question, top_k=top_k)
    if not candidates:
        return RetrievalResult(mode="traditional", query=question, chunks=[])

    chunk_ids = [c.chunk_id for c in candidates]
    rows = await asyncio.to_thread(get_rag_chunks_by_ids, chunk_ids)
    by_id = {row["chunk_id"]: row for row in rows}

    chunks: list[RetrievedChunk] = []
    warnings: list[str] = []
    for cand in candidates:  # giữ thứ tự rank của vector search
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
                vector_score=cand.score,
                sources=["vector"],
            )
        )

    return RetrievalResult(
        mode="traditional", query=question, chunks=chunks, warnings=warnings
    )
