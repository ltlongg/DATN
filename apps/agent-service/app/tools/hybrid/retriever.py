"""Hybrid retrieval: phối hợp vector + graph, fuse bằng RRF, hydrate MỘT lần, rerank.

Đây là đường mặc định cho orchestrator. Là lớp COMPOSITION (không nuốt logic của hai
mode con): gọi `search_vector` + `search_graph` lấy candidate nhẹ, RRF gộp theo RANK
(không hòa hai thang đo score gốc), hydrate Postgres một lần rồi rerank tùy chọn.

`graph_context` đi THẲNG lên kết quả, KHÔNG qua RRF (RRF chỉ xếp hạng chunk). Rule B
(citation): mọi `source_chunk_ids` của graph_context đều phải có mặt ở kết quả cuối, để mọi
fact graph dùng đều có chunk tương ứng (validator không drop nguồn). Các chunk kéo theo này
là PHẦN CỘNG THÊM, không bị `hybrid_candidate_k` hay `rerank_top_k` cắt.

Rule B áp **SAU lần cắt cuối cùng**, không phải trước. Bản trước loại sẵn chunk đã lọt top
RRF ra khỏi tập bù, nên chunk vừa là nguồn graph vừa lọt top mà rớt sau rerank thì mất trắng
— hụt đúng cam kết ngay trên. Chunk bù mang `debug={"citation_only": True}`: chúng là
PROVENANCE, gọi được ở citation nhưng người gọi nên loại khỏi context đưa vào prompt.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence

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
from app.tools.graph_rag.vector_store import search_bm25, search_vector

__all__ = ["retrieve_hybrid"]

_SOURCE_ORDER = {"vector": 0, "sparse": 1, "graph": 2}


async def _vector_candidates(
    question: str, *, top_k: int | None
) -> tuple[list[RetrievalCandidate], RetrievalBackendError | None]:
    try:
        return await search_vector(question, top_k=top_k), None
    except RetrievalBackendError as exc:
        return [], exc


async def _bm25_candidates(
    question: str, *, top_k: int | None
) -> tuple[list[RetrievalCandidate], RetrievalBackendError | None]:
    try:
        return await search_bm25(question, top_k=top_k), None
    except RetrievalBackendError as exc:
        return [], exc


async def _graph_candidates(
    seed_mentions: Sequence[str],
    *,
    top_k: int | None,
    max_seed_entities: int | None,
    max_chunks_per_seed: int | None,
    hub_source_count_threshold: int | None,
    max_context_items: int | None,
    max_path_hops: int | None,
    path_hit_weight: float | None,
) -> tuple[list[RetrievalCandidate], list[GraphContextItem], RetrievalBackendError | None]:
    try:
        candidates, context = await asyncio.to_thread(
            search_graph,
            seed_mentions,
            top_k=top_k,
            max_seed_entities=max_seed_entities,
            max_chunks_per_seed=max_chunks_per_seed,
            hub_source_count_threshold=hub_source_count_threshold,
            max_context_items=max_context_items,
            max_path_hops=max_path_hops,
            path_hit_weight=path_hit_weight,
        )
        return candidates, context, None
    except RetrievalBackendError as exc:
        return [], [], exc
    except Exception:  # thiếu env/driver hoặc kết nối Neo4j lỗi
        return [], [], RetrievalBackendError("neo4j_unavailable")


async def retrieve_hybrid(
    question: str,
    *,
    seed_mentions: Sequence[str] = (),
    rag_top_k: int | None = None,
    graph_top_k: int | None = None,
    hybrid_candidate_k: int | None = None,
    hybrid_rrf_k: int | None = None,
    rerank_top_k: int | None = None,
    bm25_top_k: int | None = None,
    graph_max_seed_entities: int | None = None,
    graph_max_chunks_per_seed: int | None = None,
    graph_hub_source_count_threshold: int | None = None,
    graph_max_context_items: int | None = None,
    graph_max_path_hops: int | None = None,
    graph_path_hit_weight: float | None = None,
) -> RetrievalResult:
    """Mọi kwarg tinh chỉnh None -> fallback settings (Cấu hình hệ thống truyền giá trị admin).
    `rag_top_k`/`bm25_top_k`/graph_* forward xuống candidate; `hybrid_candidate_k`/
    `hybrid_rrf_k`/`rerank_top_k` áp ngay trong hàm (fuse/cắt)."""
    settings = get_settings()
    rrf_k = hybrid_rrf_k if hybrid_rrf_k is not None else settings.hybrid_rrf_k
    candidate_k = (
        hybrid_candidate_k if hybrid_candidate_k is not None else settings.hybrid_candidate_k
    )
    rerank_k = rerank_top_k if rerank_top_k is not None else settings.rerank_top_k
    (
        (vec_cands, vec_err),
        (bm25_cands, bm25_err),
        (graph_cands, graph_context, graph_err),
    ) = await asyncio.gather(
        _vector_candidates(question, top_k=rag_top_k),
        _bm25_candidates(question, top_k=bm25_top_k),
        _graph_candidates(
            seed_mentions,
            top_k=graph_top_k,
            max_seed_entities=graph_max_seed_entities,
            max_chunks_per_seed=graph_max_chunks_per_seed,
            hub_source_count_threshold=graph_hub_source_count_threshold,
            max_context_items=graph_max_context_items,
            max_path_hops=graph_max_path_hops,
            path_hit_weight=graph_path_hit_weight,
        ),
    )

    # Vector + sparse cùng dựa Qdrant nên thường sống/chết cùng nhau; điều kiện "chết hẳn"
    # vẫn là vector (dense) + graph cùng lỗi. Sparse lỗi riêng -> chỉ degrade + warning.
    if vec_err is not None and graph_err is not None:
        raise RetrievalBackendError("all_backends_failed")

    warnings: list[str] = []
    if vec_err is not None:
        warnings.append(f"vector backend lỗi ({vec_err.code}), bỏ qua nguồn dense.")
    if bm25_err is not None:
        warnings.append(f"sparse backend lỗi ({bm25_err.code}), bỏ qua nguồn BM25.")
    if graph_err is not None:
        warnings.append(f"graph backend lỗi ({graph_err.code}), bỏ qua nguồn graph.")

    # --- RRF: gộp 3 nguồn theo rank, dedupe theo chunk_id ---
    rrf_score: dict[str, float] = {}
    vector_score: dict[str, float | None] = {}
    graph_score: dict[str, float | None] = {}
    sources: dict[str, set[CandidateSource]] = {}
    for cand in [*vec_cands, *bm25_cands, *graph_cands]:
        rrf_score[cand.chunk_id] = rrf_score.get(cand.chunk_id, 0.0) + 1.0 / (
            rrf_k + cand.rank
        )
        sources.setdefault(cand.chunk_id, set()).add(cand.source)
        if cand.source == "vector":
            vector_score[cand.chunk_id] = cand.score
        elif cand.source == "graph":
            graph_score[cand.chunk_id] = cand.score
        # "sparse": không có field score riêng (giữ schema gọn) — chỉ góp RRF + source.

    fused = sorted(rrf_score, key=lambda cid: (-rrf_score[cid], cid))
    top_fused = fused[:candidate_k]

    # --- Rule B: mọi chunk nguồn của graph_context phải có mặt ở kết quả CUỐI ---
    # Gom TOÀN BỘ, KHÔNG loại chunk đã lọt top RRF: chunk lọt top vẫn có thể bị rerank cắt
    # ở dưới, nên phải đợi tới sau lần cắt cuối cùng mới biết chunk nào còn thiếu.
    graph_source_ids = list(
        dict.fromkeys(cid for item in graph_context for cid in item.source_chunk_ids)
    )

    hydrate_ids = list(dict.fromkeys([*top_fused, *graph_source_ids]))
    if not hydrate_ids:
        return RetrievalResult(
            mode="hybrid", query=question, chunks=[], graph_context=graph_context, warnings=warnings
        )

    rows = await asyncio.to_thread(get_rag_chunks_by_ids, hydrate_ids)
    by_id = {row["chunk_id"]: row for row in rows}

    missing_warned: set[str] = set()

    def _build(chunk_id: str, *, citation_only: bool) -> RetrievedChunk | None:
        row = by_id.get(chunk_id)
        if row is None:
            # Warn MỘT lần/chunk: một id vừa ở top_fused vừa là nguồn graph sẽ đi qua đây 2 lần.
            if chunk_id not in missing_warned:
                missing_warned.add(chunk_id)
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

    # --- Rerank phần RRF rồi cắt rerank_top_k ---
    fused_chunks = await rerank(question, fused_chunks)
    fused_chunks = fused_chunks[:rerank_k]

    # --- Rule B áp SAU lần cắt cuối cùng: chunk nguồn graph nào chưa có mặt thì bù vào.
    # Bù ở đây (không phải trước rerank) mới đúng cam kết "PHẦN CỘNG THÊM, không bị
    # hybrid_candidate_k hay rerank_top_k cắt" — chunk lọt top_fused rồi rớt sau rerank
    # trước đây bị mất trắng vì không ai bù lại.
    final_ids = {c.chunk_id for c in fused_chunks}
    citation_chunks = [
        c
        for c in (
            _build(cid, citation_only=True)
            for cid in graph_source_ids
            if cid not in final_ids
        )
        if c
    ]
    final_chunks = fused_chunks + citation_chunks

    return RetrievalResult(
        mode="hybrid",
        query=question,
        chunks=final_chunks,
        graph_context=graph_context,
        warnings=warnings,
    )
