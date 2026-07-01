"""Test reorder_for_context: best-first -> best ở hai đầu, yếu ở giữa; giữ nguyên số chunk."""

from __future__ import annotations

from app.schemas.retrieval import RetrievedChunk
from app.tools.reorder import reorder_for_context


def _c(chunk_id: str) -> RetrievedChunk:
    return RetrievedChunk(chunk_id=chunk_id, text=chunk_id, metadata={}, heading_path=[])


def test_reorder_best_at_both_ends() -> None:
    chunks = [_c("c0"), _c("c1"), _c("c2"), _c("c3"), _c("c4")]  # c0 tốt nhất
    out = [c.chunk_id for c in reorder_for_context(chunks)]
    assert out[0] == "c0"  # tốt nhất ở đầu
    assert out[-1] == "c1"  # tốt nhì ở cuối
    assert out[2] == "c4"  # yếu nhất ở giữa
    assert out == ["c0", "c2", "c4", "c3", "c1"]


def test_reorder_preserves_all_chunks() -> None:
    chunks = [_c(f"c{i}") for i in range(7)]
    out = reorder_for_context(chunks)
    assert sorted(c.chunk_id for c in out) == sorted(c.chunk_id for c in chunks)
    assert len(out) == 7


def test_reorder_empty_and_single() -> None:
    assert reorder_for_context([]) == []
    single = [_c("only")]
    assert [c.chunk_id for c in reorder_for_context(single)] == ["only"]
