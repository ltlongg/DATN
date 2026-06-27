"""Test reranker optional (AutoModelForSequenceClassification, theo model card
AITeamVN/Vietnamese_Reranker): rỗng model -> no-op; có model -> chấm logit cặp
(query, text) rồi sort giảm dần. Mock `_score` để khỏi nạp torch/transformers thật.
"""

from __future__ import annotations

from types import SimpleNamespace

from app.core import reranker as RR
from app.schemas.retrieval import RetrievedChunk


def _chunk(chunk_id, text):
    return RetrievedChunk(chunk_id=chunk_id, text=text, metadata={}, heading_path=[])


async def test_reranker_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setattr(
        RR, "get_settings", lambda: SimpleNamespace(reranker_model="", reranker_max_length=512)
    )

    def fail_score(*a, **k):
        raise AssertionError("không được nạp model khi reranker tắt")

    monkeypatch.setattr(RR, "_score", fail_score)
    chunks = [_chunk("c-1", "a"), _chunk("c-2", "b")]
    out = await RR.rerank("q", chunks)
    assert [c.chunk_id for c in out] == ["c-1", "c-2"]  # giữ nguyên
    assert all(c.rerank_score is None for c in out)


async def test_reranker_reorders_chunks_when_enabled_with_mock(monkeypatch) -> None:
    monkeypatch.setattr(
        RR,
        "get_settings",
        lambda: SimpleNamespace(reranker_model="fake-model", reranker_max_length=2304),
    )

    captured = {}

    def fake_score(name, pairs, max_length):
        captured["name"] = name
        captured["pairs"] = pairs
        captured["max_length"] = max_length
        return [0.1, 0.9]  # c-1 thấp, c-2 cao -> đảo thứ tự

    monkeypatch.setattr(RR, "_score", fake_score)
    chunks = [_chunk("c-1", "a"), _chunk("c-2", "b")]
    out = await RR.rerank("q", chunks)

    assert [c.chunk_id for c in out] == ["c-2", "c-1"]  # sort theo logit desc
    assert out[0].rerank_score == 0.9
    # cặp (query, text) + max_length truyền đúng theo model card.
    assert captured["pairs"] == [["q", "a"], ["q", "b"]]
    assert captured["max_length"] == 2304


async def test_reranker_noop_when_no_chunks(monkeypatch) -> None:
    monkeypatch.setattr(
        RR,
        "get_settings",
        lambda: SimpleNamespace(reranker_model="fake-model", reranker_max_length=512),
    )
    monkeypatch.setattr(RR, "_score", lambda *a, **k: (_ for _ in ()).throw(AssertionError))
    assert await RR.rerank("q", []) == []
