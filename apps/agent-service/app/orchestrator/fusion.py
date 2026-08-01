"""Gộp kết quả của NHIỀU query chạy song song trong cùng một bước todo. THUẦN, không I/O.

Xem `docs/plan/agentic-retrieval-loop-plan.md` §4.2 + §4.2.1.

Hai điểm dễ làm sai, ghi lại vì cả hai đều hỏng ÂM THẦM:

1. **RRF theo RANK, không cộng score gốc.** Mỗi retriever đã rerank nội bộ và mỗi thang đo
   một bản chất (cosine / rank graph / RRF / reranker). Cộng thẳng là so hai thang khác nhau.

2. **Rule B phải áp SAU lần cắt cuối cùng.** `retrieve_hybrid` đã bảo đảm chunk nguồn
   graph_context có mặt trong kết quả CỦA MỘT QUERY, nhưng lần cắt `multiquery_final_k` ở
   đây là lần cắt MỚI, đứng sau nó — không bù lại là thủng đúng cái bug B0 vừa vá.

`citation_only` = chunk chỉ giữ làm PROVENANCE (để citation trỏ vào được), KHÔNG tính vào
hạn ngạch context và người gọi nên loại khỏi prompt. Chunk như vậy không tham gia xếp hạng
RRF: nó vốn không được chọn vì liên quan, mà vì có fact graph trỏ tới.
"""

from __future__ import annotations

from app.schemas.retrieval import GraphContextItem, RetrievalResult, RetrievedChunk

__all__ = ["fuse_query_results", "is_citation_only", "answer_context_chunks"]


def is_citation_only(chunk: RetrievedChunk) -> bool:
    return bool(chunk.debug.get("citation_only"))


def answer_context_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Phần đưa vào prompt: bỏ chunk provenance-only (chúng đã có mặt qua graph_context,
    kèm chunk_id nguồn, nên LLM vẫn trích dẫn được mà không cần đọc toàn văn)."""
    return [c for c in chunks if not is_citation_only(c)]


def _as_provenance(chunk: RetrievedChunk) -> RetrievedChunk:
    if is_citation_only(chunk):
        return chunk
    return chunk.model_copy(update={"debug": {**chunk.debug, "citation_only": True}})


def _merge_graph_context(results: list[RetrievalResult]) -> list[GraphContextItem]:
    merged: dict[tuple[str, ...], GraphContextItem] = {}
    for result in results:
        for item in result.graph_context:
            merged.setdefault(item.dedup_key(), item)
    return list(merged.values())


def fuse_query_results(
    results: list[RetrievalResult], *, rrf_k: int, final_k: int
) -> tuple[list[RetrievedChunk], list[GraphContextItem]]:
    """Gộp N kết quả -> (chunks, graph_context).

    `chunks` = top `final_k` chunk answer-context theo RRF cross-query, cộng thêm chunk
    provenance của graph_context chưa có mặt (Rule B — KHÔNG tính vào `final_k`).
    """
    if not results:
        return [], []

    graph_context = _merge_graph_context(results)

    scores: dict[str, float] = {}
    pool: dict[str, RetrievedChunk] = {}
    for result in results:
        rank = 0
        for chunk in result.chunks:
            if is_citation_only(chunk):
                # Giữ lại phòng khi Rule B cần, nhưng KHÔNG cho chiếm suất answer-context.
                pool.setdefault(chunk.chunk_id, chunk)
                continue
            rank += 1
            scores[chunk.chunk_id] = scores.get(chunk.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            # Bản answer-context thắng bản provenance của query khác (cùng chunk_id).
            existing = pool.get(chunk.chunk_id)
            if existing is None or is_citation_only(existing):
                pool[chunk.chunk_id] = chunk

    ordered = sorted(scores, key=lambda cid: (-scores[cid], cid))[:final_k]
    fused = [pool[cid] for cid in ordered]

    kept = set(ordered)
    provenance = [
        _as_provenance(pool[cid])
        for cid in dict.fromkeys(
            cid for item in graph_context for cid in item.source_chunk_ids
        )
        if cid not in kept and cid in pool
    ]
    return fused + provenance, graph_context
