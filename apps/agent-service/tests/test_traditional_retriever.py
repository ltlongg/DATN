"""Test retrieve_traditional: vector candidates -> hydrate Postgres -> RetrievedChunk,
giữ thứ tự rank, bỏ chunk thiếu (+warning), graph_context luôn rỗng.
"""

from __future__ import annotations

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


def _patch(monkeypatch, candidates, rows):
    async def fake_search(question, *, top_k=None, client=None):
        return candidates

    monkeypatch.setattr(R, "search_vector", fake_search)
    monkeypatch.setattr(R, "get_rag_chunks_by_ids", lambda ids: rows)


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
