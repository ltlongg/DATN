"""Test search_vector(): Qdrant payload -> RetrievalCandidate, lỗi -> backend error.

Mock cả embed (khỏi nạp model thật) lẫn Qdrant client (khỏi cần backend remote).
"""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from app.schemas.retrieval import RetrievalBackendError
from app.tools.graph_rag import vector_store as V


class _FakeQdrant:
    """Client giả: query_points trả các point cho sẵn."""

    def __init__(self, points: list[SimpleNamespace]) -> None:
        self._points = points
        self.calls: list[dict] = []

    def query_points(self, **kwargs):  # noqa: ANN003
        self.calls.append(kwargs)
        return SimpleNamespace(points=self._points)


def _point(point_id, score, payload):
    return SimpleNamespace(id=point_id, score=score, payload=payload)


@pytest.fixture(autouse=True)
def _stub_embed(monkeypatch):
    async def fake_embed(texts):
        return np.ones((len(texts), 4), dtype=np.float32)

    monkeypatch.setattr(V, "embed_texts", fake_embed)


async def test_search_vector_returns_candidates_from_qdrant_payload() -> None:
    client = _FakeQdrant(
        [
            _point("u1", 0.92, {"chunk_id": "c-1"}),
            _point("u2", 0.81, {"chunk_id": "c-2"}),
        ]
    )
    cands = await V.search_vector("Trương Định", top_k=5, client=client)
    assert [c.chunk_id for c in cands] == ["c-1", "c-2"]
    assert [c.rank for c in cands] == [1, 2]
    assert cands[0].source == "vector"
    assert cands[0].score == pytest.approx(0.92)
    # top_k truyền xuống Qdrant.
    assert client.calls[0]["limit"] == 5


async def test_search_vector_skips_point_missing_chunk_id() -> None:
    client = _FakeQdrant(
        [
            _point("u1", 0.92, {"chunk_id": "c-1"}),
            _point("u2", 0.81, {}),  # thiếu chunk_id -> bỏ
            _point("u3", 0.70, {"chunk_id": "c-3"}),
        ]
    )
    cands = await V.search_vector("x", top_k=5, client=client)
    assert [c.chunk_id for c in cands] == ["c-1", "c-3"]
    # rank vẫn liền mạch sau khi bỏ point hỏng.
    assert [c.rank for c in cands] == [1, 2]


async def test_search_vector_raises_qdrant_unavailable_on_client_error() -> None:
    class _Broken:
        def query_points(self, **kwargs):  # noqa: ANN003
            raise ConnectionError("boom")

    with pytest.raises(RetrievalBackendError) as exc:
        await V.search_vector("x", client=_Broken())
    assert exc.value.code == "qdrant_unavailable"


async def test_search_vector_raises_embedding_failed(monkeypatch) -> None:
    async def boom(texts):
        raise RuntimeError("model down")

    monkeypatch.setattr(V, "embed_texts", boom)
    with pytest.raises(RetrievalBackendError) as exc:
        await V.search_vector("x", client=_FakeQdrant([]))
    assert exc.value.code == "embedding_failed"
