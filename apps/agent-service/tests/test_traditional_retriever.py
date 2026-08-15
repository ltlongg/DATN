"""Test retrieve_traditional: dense+sparse fuse candidates -> hydrate Postgres ->
RetrievedChunk -> rerank + cắt rerank_top_k. Bỏ chunk thiếu (+warning), graph_context rỗng.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.schemas.retrieval import RetrievalCandidate
from app.tools.traditional_rag import retriever as R

def _cand(chunk_id, rank, score):
    return RetrievalCandidate(chunk_id=chunk_id, source="vector", rank=rank, score=score)

def _row(chunk_id, text="t"):
    return {
        "chunk_id": chunk_id,
        "text": text,
        "metadata": {"k": "v"},
        "heading_path": ["h1", "h2"],
    }

def _patch(monkeypatch, candidates, rows, *, rerank_fn=None, rerank_top_k=8):
    async def fake_search(question, *, top_k=None, bm25_top_k=None, client=None):
        return candidates

    async def passthrough_rerank(question, chunks):
        return chunks

    monkeypatch.setattr(R, "search_dense_sparse", fake_search)
    monkeypatch.setattr(R, "get_rag_chunks_by_ids", lambda ids: rows)
    monkeypatch.setattr(R, "rerank", rerank_fn or passthrough_rerank)
    monkeypatch.setattr(R, "get_settings", lambda: SimpleNamespace(rerank_top_k=rerank_top_k))

async def test_retrieve_traditional_hydrates_candidates_into_chunks(monkeypatch) -> None:
    _patch(
        monkeypatch,
        [_cand("c-1", 1, 0.9), _cand("c-2", 2, 0.7)],
        [_row("c-1"), _row("c-2")],
    )
    result = await R.retrieve_traditional("Trương Định")
    assert result.mode == "traditional"
    assert [c.chunk_id for c in result.chunks] == ["c-1", "c-2"]
    assert result.chunks[0].vector_score == 0.9
    assert result.chunks[0].sources == ["vector"]
    assert result.chunks[0].heading_path == ["h1", "h2"]
    assert result.graph_context == []  # traditional KHÔNG điền graph_context

async def test_retrieve_traditional_skips_missing_hydrated_chunk(monkeypatch) -> None:
    # candidate c-2 không có row trong Postgres -> bỏ + warning.
    _patch(monkeypatch, [_cand("c-1", 1, 0.9), _cand("c-2", 2, 0.7)], [_row("c-1")])
    result = await R.retrieve_traditional("x")
    assert [c.chunk_id for c in result.chunks] == ["c-1"]
    assert any("c-2" in w for w in result.warnings)

async def test_retrieve_traditional_empty_when_no_candidates(monkeypatch) -> None:
    _patch(monkeypatch, [], [])
    result = await R.retrieve_traditional("câu hỏi mơ hồ")
    assert result.chunks == []
    assert result.graph_context == []

async def test_retrieve_traditional_forwards_tuning(monkeypatch) -> None:
    seen: dict = {}

    async def fake_search(question, *, top_k=None, bm25_top_k=None, client=None):
        seen["top_k"] = top_k
        seen["bm25_top_k"] = bm25_top_k
        return [_cand("c-1", 1, 0.9), _cand("c-2", 2, 0.8), _cand("c-3", 3, 0.7)]

    async def passthrough(question, chunks):
        return chunks

    monkeypatch.setattr(R, "search_dense_sparse", fake_search)
    monkeypatch.setattr(
        R, "get_rag_chunks_by_ids", lambda ids: [_row("c-1"), _row("c-2"), _row("c-3")]
    )
    monkeypatch.setattr(R, "rerank", passthrough)
    # rerank_top_k=2 truyền thẳng -> KHÔNG chạm get_settings; forward top_k/bm25_top_k xuống search.
    result = await R.retrieve_traditional("q", top_k=11, bm25_top_k=9, rerank_top_k=2)
    assert seen == {"top_k": 11, "bm25_top_k": 9}
    assert [c.chunk_id for c in result.chunks] == ["c-1", "c-2"]  # cắt còn rerank_top_k=2

async def test_retrieve_traditional_reranks_then_cuts(monkeypatch) -> None:
    # rerank đảo thứ tự (c-3 lên đầu) rồi cắt rerank_top_k=2 -> [c-3, c-2].
    async def fake_rerank(question, chunks):
        return list(reversed(chunks))

    _patch(
        monkeypatch,
        [_cand("c-1", 1, 0.9), _cand("c-2", 2, 0.5), _cand("c-3", 3, 0.1)],
        [_row("c-1"), _row("c-2"), _row("c-3")],
        rerank_fn=fake_rerank,
        rerank_top_k=2,
    )
    result = await R.retrieve_traditional("q")
    assert [c.chunk_id for c in result.chunks] == ["c-3", "c-2"]
