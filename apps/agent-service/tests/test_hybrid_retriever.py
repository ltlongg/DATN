"""Test retrieve_hybrid: RRF dedupe/fuse, hydrate MỘT lần theo thứ tự fused, graph_context
đi thẳng (không qua RRF), rule B kéo chunk nguồn của graph_context để giữ citation,
partial khi một backend lỗi, raise khi cả hai chết.
"""

from __future__ import annotations

import pytest

from app.schemas.retrieval import (
    GraphContextItem,
    RetrievalBackendError,
    RetrievalCandidate,
)
from app.tools.hybrid import retriever as H


def _vc(chunk_id, rank, score=0.5):
    return RetrievalCandidate(chunk_id=chunk_id, source="vector", rank=rank, score=score)


def _gc(chunk_id, rank, score=2.0):
    return RetrievalCandidate(chunk_id=chunk_id, source="graph", rank=rank, score=score)


def _row(chunk_id):
    return {"chunk_id": chunk_id, "text": f"text {chunk_id}", "metadata": {}, "heading_path": []}


def _patch(monkeypatch, *, vector=None, graph=None, vector_err=None, graph_err=None, rows=None):
    available = {r["chunk_id"]: r for r in (rows or [])}
    calls = {"hydrate": 0}

    async def fake_vector(question, *, top_k=None, client=None):
        if vector_err:
            raise vector_err
        return vector or []

    def fake_graph(query, *, seed_mentions=None, **kw):
        if graph_err:
            raise graph_err
        return graph if graph is not None else ([], [])

    def fake_hydrate(ids):
        calls["hydrate"] += 1
        return [available[i] for i in ids if i in available]

    async def passthrough_rerank(question, chunks):
        return chunks

    monkeypatch.setattr(H, "search_vector", fake_vector)
    monkeypatch.setattr(H, "search_graph", fake_graph)
    monkeypatch.setattr(H, "get_rag_chunks_by_ids", fake_hydrate)
    monkeypatch.setattr(H, "rerank", passthrough_rerank)
    return calls


async def test_hybrid_rrf_dedupes_same_chunk_from_vector_and_graph(monkeypatch) -> None:
    _patch(
        monkeypatch,
        vector=[_vc("c-1", 1), _vc("c-2", 2)],
        graph=([_gc("c-3", 1), _gc("c-2", 2)], []),
        rows=[_row("c-1"), _row("c-2"), _row("c-3")],
    )
    result = await H.retrieve_hybrid("q")
    ids = [c.chunk_id for c in result.chunks]
    assert ids.count("c-2") == 1  # dedupe: c-2 chỉ xuất hiện một lần
    assert ids[0] == "c-2"  # c-2 được cả hai nguồn trỏ -> RRF cao nhất
    c2 = next(c for c in result.chunks if c.chunk_id == "c-2")
    assert set(c2.sources) == {"vector", "graph"}
    assert c2.rrf_score is not None


async def test_hybrid_hydrates_chunks_once_in_fused_order(monkeypatch) -> None:
    calls = _patch(
        monkeypatch,
        vector=[_vc("c-1", 1), _vc("c-2", 2)],
        graph=([_gc("c-3", 1), _gc("c-2", 2)], []),
        rows=[_row("c-1"), _row("c-2"), _row("c-3")],
    )
    result = await H.retrieve_hybrid("q")
    assert calls["hydrate"] == 1  # KHÔNG N+1
    # fused: c-2 (2 nguồn) > c-1, c-3 (bằng điểm -> tie-break chunk_id asc).
    assert [c.chunk_id for c in result.chunks] == ["c-2", "c-1", "c-3"]


async def test_hybrid_passes_graph_context_through_without_rrf(monkeypatch) -> None:
    ctx = [
        GraphContextItem(
            kind="relation",
            source_norm="a",
            target_norm="b",
            keyword="k",
            description="d",
            source_chunk_ids=["c-1"],
        )
    ]
    _patch(
        monkeypatch,
        vector=[_vc("c-1", 1)],
        graph=([_gc("c-1", 1)], ctx),
        rows=[_row("c-1")],
    )
    result = await H.retrieve_hybrid("q")
    assert len(result.graph_context) == 1
    assert result.graph_context[0].keyword == "k"  # đi thẳng, không bị RRF đụng


async def test_hybrid_hydrates_graph_context_source_chunks_for_citation(monkeypatch) -> None:
    # c-99 là nguồn của graph_context nhưng KHÔNG nằm trong candidate RRF -> rule B vẫn
    # phải hydrate nó để citation không bị validator drop.
    ctx = [
        GraphContextItem(
            kind="entity",
            name="X",
            norm_name="x",
            description="d",
            source_chunk_ids=["c-99"],
        )
    ]
    _patch(
        monkeypatch,
        vector=[_vc("c-1", 1)],
        graph=([_gc("c-1", 1)], ctx),
        rows=[_row("c-1"), _row("c-99")],
    )
    result = await H.retrieve_hybrid("q")
    ids = [c.chunk_id for c in result.chunks]
    assert "c-99" in ids  # kéo theo từ graph_context
    c99 = next(c for c in result.chunks if c.chunk_id == "c-99")
    assert "graph" in c99.sources


async def test_hybrid_partial_when_qdrant_fails_but_graph_succeeds(monkeypatch) -> None:
    _patch(
        monkeypatch,
        vector_err=RetrievalBackendError("qdrant_unavailable"),
        graph=([_gc("c-3", 1)], []),
        rows=[_row("c-3")],
    )
    result = await H.retrieve_hybrid("q")
    assert [c.chunk_id for c in result.chunks] == ["c-3"]
    assert any("qdrant" in w for w in result.warnings)


async def test_hybrid_vector_only_when_graph_empty(monkeypatch) -> None:
    _patch(monkeypatch, vector=[_vc("c-1", 1)], graph=([], []), rows=[_row("c-1")])
    result = await H.retrieve_hybrid("q")
    assert [c.chunk_id for c in result.chunks] == ["c-1"]


async def test_hybrid_raises_when_all_backends_fail(monkeypatch) -> None:
    _patch(
        monkeypatch,
        vector_err=RetrievalBackendError("qdrant_unavailable"),
        graph_err=ConnectionError("neo4j down"),
    )
    with pytest.raises(RetrievalBackendError) as exc:
        await H.retrieve_hybrid("q")
    assert exc.value.code == "all_backends_failed"


async def test_hybrid_skips_missing_hydrated_chunk_with_warning(monkeypatch) -> None:
    _patch(
        monkeypatch,
        vector=[_vc("c-1", 1), _vc("c-2", 2)],
        graph=([], []),
        rows=[_row("c-1")],  # c-2 thiếu trong Postgres
    )
    result = await H.retrieve_hybrid("q")
    assert [c.chunk_id for c in result.chunks] == ["c-1"]
    assert any("c-2" in w for w in result.warnings)
