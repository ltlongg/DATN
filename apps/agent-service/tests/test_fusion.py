"""Test `orchestrator/fusion.py` — RRF cross-query + tái áp Rule B sau lần cắt. Thuần."""

from __future__ import annotations

from app.orchestrator.fusion import (
    answer_context_chunks,
    fuse_query_results,
    is_citation_only,
)
from app.schemas.retrieval import GraphContextItem, RetrievalResult, RetrievedChunk

RRF_K = 60


def _chunk(chunk_id: str, *, citation_only: bool = False) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        text=f"text {chunk_id}",
        metadata={},
        heading_path=[],
        debug={"citation_only": True} if citation_only else {},
    )


def _result(*chunk_ids, graph_context=None, citation_only=()) -> RetrievalResult:
    return RetrievalResult(
        mode="hybrid",
        query="q",
        chunks=[_chunk(c, citation_only=c in citation_only) for c in chunk_ids],
        graph_context=list(graph_context or []),
    )


def _ctx(*chunk_ids, norm="x") -> GraphContextItem:
    return GraphContextItem(
        kind="entity",
        name=norm.upper(),
        norm_name=norm,
        description="d",
        source_chunk_ids=list(chunk_ids),
    )


def _fuse(results, *, final_k=8):
    return fuse_query_results(results, rrf_k=RRF_K, final_k=final_k)


# --- RRF cross-query ---


def test_empty_results_returns_empty() -> None:
    assert _fuse([]) == ([], [])


def test_single_query_preserves_order() -> None:
    chunks, _ = _fuse([_result("c-1", "c-2", "c-3")])
    assert [c.chunk_id for c in chunks] == ["c-1", "c-2", "c-3"]


def test_chunk_hit_by_two_queries_outranks_single_hit_top1() -> None:
    """c-shared ở hạng 2 của CẢ HAI query -> tổng RRF > c-a (hạng 1 của một query).

    1/62 + 1/62 = 0.03226 > 1/61 = 0.01639.
    """
    chunks, _ = _fuse([_result("c-a", "c-shared"), _result("c-b", "c-shared")])
    assert [c.chunk_id for c in chunks][0] == "c-shared"


def test_dedupe_keeps_one_entry_per_chunk_id() -> None:
    chunks, _ = _fuse([_result("c-1", "c-2"), _result("c-2", "c-3")])
    ids = [c.chunk_id for c in chunks]
    assert sorted(ids) == ["c-1", "c-2", "c-3"]
    assert len(ids) == len(set(ids))


def test_tie_break_is_deterministic_by_chunk_id() -> None:
    chunks, _ = _fuse([_result("c-b"), _result("c-a")])  # cùng hạng 1 -> cùng điểm
    assert [c.chunk_id for c in chunks] == ["c-a", "c-b"]


def test_final_k_cuts_answer_context() -> None:
    chunks, _ = _fuse([_result(*[f"c-{i}" for i in range(10)])], final_k=3)
    assert [c.chunk_id for c in chunks] == ["c-0", "c-1", "c-2"]


# --- graph_context merge ---


def test_graph_context_deduped_across_queries() -> None:
    _, ctx = _fuse(
        [
            _result("c-1", graph_context=[_ctx("c-9", norm="a")]),
            _result("c-2", graph_context=[_ctx("c-9", norm="a"), _ctx("c-8", norm="b")]),
        ]
    )
    assert [i.norm_name for i in ctx] == ["a", "b"]


# --- Rule B: chunk nguồn graph sống sót lần cắt final_k ---


def test_graph_source_chunk_readded_after_cut_as_provenance() -> None:
    results = [_result(*[f"c-{i}" for i in range(10)], graph_context=[_ctx("c-9")])]
    chunks, _ = _fuse(results, final_k=3)
    ids = [c.chunk_id for c in chunks]
    assert ids[:3] == ["c-0", "c-1", "c-2"]  # answer-context vẫn bị cắt đúng final_k
    assert "c-9" in ids  # nhưng nguồn graph được bù lại
    assert is_citation_only(chunks[ids.index("c-9")])


def test_rule_b_addition_does_not_count_against_final_k() -> None:
    results = [_result(*[f"c-{i}" for i in range(10)], graph_context=[_ctx("c-9", "c-8")])]
    chunks, _ = _fuse(results, final_k=3)
    assert len(answer_context_chunks(chunks)) == 3  # đúng trần
    assert len(chunks) == 5  # 3 + 2 provenance -> TỔNG vượt trần là ĐÚNG


def test_graph_source_already_in_top_is_not_duplicated_nor_demoted() -> None:
    results = [_result("c-0", "c-1", graph_context=[_ctx("c-0")])]
    chunks, _ = _fuse(results, final_k=8)
    assert [c.chunk_id for c in chunks] == ["c-0", "c-1"]
    assert not is_citation_only(chunks[0])  # vẫn là answer-context, không bị hạ cấp


def test_graph_source_missing_from_pool_is_skipped() -> None:
    """graph_context trỏ tới chunk không retriever nào trả về -> bỏ qua, KHÔNG dựng chunk rỗng."""
    chunks, _ = _fuse([_result("c-1", graph_context=[_ctx("khong-ton-tai")])])
    assert [c.chunk_id for c in chunks] == ["c-1"]


# --- citation_only không chiếm suất answer-context ---


def test_citation_only_chunk_does_not_consume_final_k_slot() -> None:
    results = [_result("prov", "c-0", "c-1", citation_only=("prov",))]
    chunks, _ = _fuse(results, final_k=2)
    # "prov" không được tính hạng nên c-0/c-1 vẫn đủ 2 suất; "prov" bị bỏ vì
    # không graph_context nào trỏ tới nó ở test này.
    assert [c.chunk_id for c in chunks] == ["c-0", "c-1"]


def test_citation_only_does_not_shift_ranks_of_answer_chunks() -> None:
    """Chunk provenance nằm ĐẦU list không được đẩy hạng của chunk answer xuống."""
    with_prov = _result("prov", "c-x", citation_only=("prov",))
    without = _result("c-x")
    a, _ = _fuse([with_prov])
    b, _ = _fuse([without])
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b] == ["c-x"]


def test_answer_version_wins_over_provenance_version_of_same_chunk() -> None:
    results = [
        _result("c-1", citation_only=("c-1",)),  # query 1 chỉ có nó làm provenance
        _result("c-1"),  # query 2 xếp hạng nó bình thường
    ]
    chunks, _ = _fuse(results)
    assert [c.chunk_id for c in chunks] == ["c-1"]
    assert not is_citation_only(chunks[0])


def test_answer_context_chunks_filters_provenance() -> None:
    chunks = [_chunk("a"), _chunk("b", citation_only=True)]
    assert [c.chunk_id for c in answer_context_chunks(chunks)] == ["a"]
