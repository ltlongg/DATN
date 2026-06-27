"""Test retrieve_graph: hydrate candidate + đính graph_context, truyền seed_mentions
xuyên suốt, empty khi no seed, backend lỗi -> neo4j_unavailable.
"""

from __future__ import annotations

import pytest

from app.schemas.retrieval import (
    GraphContextItem,
    RetrievalBackendError,
    RetrievalCandidate,
)
from app.tools.graph_rag import retriever as GR


def _cand(chunk_id, rank, score):
    return RetrievalCandidate(chunk_id=chunk_id, source="graph", rank=rank, score=score)


def _row(chunk_id):
    return {"chunk_id": chunk_id, "text": "t", "metadata": {}, "heading_path": ["h"]}


def _ctx():
    return [
        GraphContextItem(
            kind="relation",
            source_name="Phan Bội Châu",
            source_norm="phan bội châu",
            target_name="Cường Để",
            target_norm="cường để",
            keyword="ủng hộ",
            description="d",
            source_chunk_ids=["c-1"],
        )
    ]


async def test_retrieve_graph_hydrates_and_attaches_graph_context(monkeypatch) -> None:
    monkeypatch.setattr(
        GR, "search_graph", lambda q, **kw: ([_cand("c-1", 1, 3.0)], _ctx())
    )
    monkeypatch.setattr(GR, "get_rag_chunks_by_ids", lambda ids: [_row("c-1")])
    result = await GR.retrieve_graph("Phan Bội Châu và Cường Để", seed_mentions=["Phan Bội Châu"])
    assert result.mode == "graph"
    assert [c.chunk_id for c in result.chunks] == ["c-1"]
    assert result.chunks[0].graph_score == 3.0
    assert result.chunks[0].sources == ["graph"]
    assert len(result.graph_context) == 1
    assert result.graph_context[0].keyword == "ủng hộ"


async def test_retrieve_graph_empty_when_no_seed(monkeypatch) -> None:
    monkeypatch.setattr(GR, "search_graph", lambda q, **kw: ([], []))
    monkeypatch.setattr(GR, "get_rag_chunks_by_ids", lambda ids: [])
    result = await GR.retrieve_graph("không có thực thể", seed_mentions=["Lạ"])
    assert result.chunks == [] and result.graph_context == []


async def test_retrieve_graph_passes_injected_seed_mentions(monkeypatch) -> None:
    seen = {}

    def fake_search(q, *, seed_mentions=None, **kw):
        seen["seed_mentions"] = seed_mentions
        return [], []

    monkeypatch.setattr(GR, "search_graph", fake_search)
    monkeypatch.setattr(GR, "get_rag_chunks_by_ids", lambda ids: [])
    await GR.retrieve_graph("x", seed_mentions=["Trương Định"])
    assert seen["seed_mentions"] == ["Trương Định"]


async def test_retrieve_graph_falls_back_to_token_match_when_none(monkeypatch) -> None:
    seen = {}

    def fake_search(q, *, seed_mentions=None, **kw):
        seen["seed_mentions"] = seed_mentions
        return [], []

    monkeypatch.setattr(GR, "search_graph", fake_search)
    monkeypatch.setattr(GR, "get_rag_chunks_by_ids", lambda ids: [])
    await GR.retrieve_graph("Trương Định là ai")  # không truyền seed_mentions
    assert seen["seed_mentions"] is None  # search_graph tự token-match


async def test_retrieve_graph_raises_neo4j_unavailable_on_backend_error(monkeypatch) -> None:
    def boom(q, **kw):
        raise ConnectionError("neo4j down")

    monkeypatch.setattr(GR, "search_graph", boom)
    with pytest.raises(RetrievalBackendError) as exc:
        await GR.retrieve_graph("x", seed_mentions=["A"])
    assert exc.value.code == "neo4j_unavailable"
