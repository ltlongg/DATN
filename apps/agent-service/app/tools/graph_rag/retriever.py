"""GraphRAG facade: seed match -> 1-hop expand -> hydrate Postgres -> RetrievalResult.

`search_graph` (sync, Neo4j) chạy trong `to_thread` để không chẹn event loop. Trả CẢ
`chunks` (provenance) LẪN `graph_context` (content đã chưng cất từ KG, đưa thẳng cho LLM).
`seed_mentions` injectable: caller (orchestrator) truyền mention từ LLM; None -> search_graph
tự token-match. Không match seed -> empty result (KHÔNG raise).
"""

from __future__ import annotations

import asyncio

from app.schemas.retrieval import RetrievalBackendError, RetrievalResult, RetrievedChunk
from app.tools.graph_rag.chunk_store import get_rag_chunks_by_ids
from app.tools.graph_rag.graph_store import search_graph

__all__ = ["retrieve_graph"]


async def retrieve_graph(
    query: str,
    *,
    seed_mentions: list[str] | None = None,
    graph_top_k: int | None = None,
    graph_max_seed_entities: int | None = None,
    graph_max_chunks_per_seed: int | None = None,
    graph_hub_source_count_threshold: int | None = None,
    graph_max_context_items: int | None = None,
    graph_max_path_hops: int | None = None,
    graph_path_hit_weight: float | None = None,
) -> RetrievalResult:
    """Các kwarg tinh chỉnh None -> search_graph fallback settings (Cấu hình hệ thống)."""
    try:
        candidates, graph_context = await asyncio.to_thread(
            search_graph,
            query,
            seed_mentions=seed_mentions,
            top_k=graph_top_k,
            max_seed_entities=graph_max_seed_entities,
            max_chunks_per_seed=graph_max_chunks_per_seed,
            hub_source_count_threshold=graph_hub_source_count_threshold,
            max_context_items=graph_max_context_items,
            max_path_hops=graph_max_path_hops,
            path_hit_weight=graph_path_hit_weight,
        )
    except RetrievalBackendError:
        raise
    except Exception as exc:  # thiếu env/driver hoặc kết nối Neo4j lỗi
        raise RetrievalBackendError("neo4j_unavailable") from exc

    chunks: list[RetrievedChunk] = []
    warnings: list[str] = []
    if candidates:
        chunk_ids = [c.chunk_id for c in candidates]
        rows = await asyncio.to_thread(get_rag_chunks_by_ids, chunk_ids)
        by_id = {row["chunk_id"]: row for row in rows}
        for cand in candidates:
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
                    graph_score=cand.score,
                    sources=["graph"],
                )
            )

    return RetrievalResult(
        mode="graph",
        query=query,
        chunks=chunks,
        graph_context=graph_context,
        warnings=warnings,
    )
