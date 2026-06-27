"""Hybrid retrieval: phối hợp vector + graph, fuse bằng RRF, hydrate MỘT lần, rerank.

Đây là đường mặc định cho orchestrator. Là lớp COMPOSITION (không nuốt logic của hai
mode con): gọi `search_vector` + `search_graph` lấy candidate nhẹ, RRF gộp theo RANK
(không hòa hai thang đo score gốc), hydrate Postgres một lần rồi rerank tùy chọn.

`graph_context` đi THẲNG lên kết quả, KHÔNG qua RRF (RRF chỉ xếp hạng chunk). Rule B
(citation): union `source_chunk_ids` của graph_context vào tập hydrate — kể cả khi chúng
không lọt top RRF — để mọi fact graph dùng đều có chunk tương ứng trong context (validator
không drop nguồn). Các chunk kéo theo này là PHẦN CỘNG THÊM, không bị `hybrid_candidate_k`
hay `rerank_top_k` cắt.
"""

from __future__ import annotations

import asyncio

from app.core.config import get_settings
from app.core.reranker import rerank
from app.schemas.retrieval import (
    CandidateSource,
    GraphContextItem,
    RetrievalBackendError,
    RetrievalCandidate,
    RetrievalResult,
    RetrievedChunk,
)
from app.tools.graph_rag.chunk_store import get_rag_chunks_by_ids
from app.tools.graph_rag.graph_store import search_graph
from app.tools.graph_rag.vector_store import search_vector

__all__ = ["retrieve_hybrid"]

_SOURCE_ORDER = {"vector": 0, "graph": 1}


async def _vector_candidates(
    question: str,
) -> tuple[list[RetrievalCandidate], RetrievalBackendError | None]:
    try:
        return await search_vector(question), None
    except RetrievalBackendError as exc:
        return [], exc


async def _graph_candidates(
    question: str, seed_mentions: list[str] | None
) -> tuple[list[RetrievalCandidate], list[GraphContextItem], RetrievalBackendError | None]:
    try:
        candidates, context = await asyncio.to_thread(
            search_graph, question, seed_mentions=seed_mentions
        )
        return candidates, context, None
    except RetrievalBackendError as exc:
        return [], [], exc
    except Exception:  # thiếu env/driver hoặc kết nối Neo4j lỗi
        return [], [], RetrievalBackendError("neo4j_unavailable")


async def retrieve_hybrid(
    question: str, *, seed_mentions: list[str] | None = None
) -> RetrievalResult:
    settings = get_settings()
    (vec_cands, vec_err), (graph_cands, graph_context, graph_err) = await asyncio.gather(
        _vector_candidates(question),
        _graph_candidates(question, seed_mentions),
    )

    if vec_err is not None and graph_err is not None:
        raise RetrievalBackendError("all_backends_failed")

    warnings: list[str] = []
    if vec_err is not None:
        warnings.append(f"vector backend lỗi ({vec_err.code}), chỉ dùng graph.")
    if graph_err is not None:
        warnings.append(f"graph backend lỗi ({graph_err.code}), chỉ dùng vector.")

    # --- RRF: gộp theo rank, dedupe theo chunk_id ---
    rrf_score: dict[str, float] = {}
    vector_score: dict[str, float | None] = {}
    graph_score: dict[str, float | None] = {}
    sources: dict[str, set[CandidateSource]] = {}
    for cand in [*vec_cands, *graph_cands]:
        rrf_score[cand.chunk_id] = rrf_score.get(cand.chunk_id, 0.0) + 1.0 / (
            settings.hybrid_rrf_k + cand.rank
        )
        sources.setdefault(cand.chunk_id, set()).add(cand.source)
        if cand.source == "vector":
            vector_score[cand.chunk_id] = cand.score
        else:
            graph_score[cand.chunk_id] = cand.score

    fused = sorted(rrf_score, key=lambda cid: (-rrf_score[cid], cid))
    top_fused = fused[: settings.hybrid_candidate_k]
    top_fused_set = set(top_fused)

    # --- Rule B: kéo chunk nguồn của graph_context (ngoài top RRF) để giữ citation ---
    citation_ids: list[str] = []
    seen_citation: set[str] = set()
    for item in graph_context:
        for chunk_id in item.source_chunk_ids:
            if chunk_id not in top_fused_set and chunk_id not in seen_citation:
                seen_citation.add(chunk_id)
                citation_ids.append(chunk_id)

    hydrate_ids = [*top_fused, *citation_ids]
    if not hydrate_ids:
        return RetrievalResult(
            mode="hybrid", query=question, chunks=[], graph_context=graph_context, warnings=warnings
        )

    rows = await asyncio.to_thread(get_rag_chunks_by_ids, hydrate_ids)
    by_id = {row["chunk_id"]: row for row in rows}

    def _build(chunk_id: str, *, citation_only: bool) -> RetrievedChunk | None:
        row = by_id.get(chunk_id)
        if row is None:
            warnings.append(f"chunk thiếu trong Postgres: {chunk_id}")
            return None
        src = sources.get(chunk_id, set())
        if citation_only:
            src = src | {"graph"}  # chunk nguồn graph_context tính là nguồn graph
        ordered = sorted(src, key=lambda s: _SOURCE_ORDER[s])
        return RetrievedChunk(
            chunk_id=row["chunk_id"],
            text=row["text"],
            metadata=row.get("metadata") or {},
            heading_path=row.get("heading_path") or [],
            vector_score=vector_score.get(chunk_id),
            graph_score=graph_score.get(chunk_id),
            rrf_score=rrf_score.get(chunk_id),
            sources=ordered,
            debug={"citation_only": True} if citation_only else {},
        )

    fused_chunks = [c for c in (_build(cid, citation_only=False) for cid in top_fused) if c]
    citation_chunks = [
        c for c in (_build(cid, citation_only=True) for cid in citation_ids) if c
    ]

    # --- Rerank phần RRF rồi cắt rerank_top_k; citation chunk là phần CỘNG THÊM ---
    fused_chunks = await rerank(question, fused_chunks)
    fused_chunks = fused_chunks[: settings.rerank_top_k]
    final_ids = {c.chunk_id for c in fused_chunks}
    final_chunks = fused_chunks + [c for c in citation_chunks if c.chunk_id not in final_ids]

    return RetrievalResult(
        mode="hybrid",
        query=question,
        chunks=final_chunks,
        graph_context=graph_context,
        warnings=warnings,
    )
