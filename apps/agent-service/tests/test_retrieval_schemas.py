"""Test contract retrieval (schemas/retrieval.py) + config knobs.

Chỉ kiểm các invariant THỰC SỰ có logic: default rỗng/None đúng chỗ (vector vs graph
không lẫn score), `dedup_key` của GraphContextItem khớp khóa cấu trúc plan chốt, và
RetrievalBackendError mang code phân loại được. Config: các knob retrieval có default.
"""

from __future__ import annotations

from app.core.config import get_settings
from app.schemas.retrieval import (
    GraphContextItem,
    RetrievalBackendError,
    RetrievalCandidate,
    RetrievalResult,
    RetrievedChunk,
)

def test_retrieval_result_defaults_graph_context_and_warnings_empty() -> None:
    result = RetrievalResult(mode="traditional", query="x", chunks=[])
    assert result.graph_context == []
    assert result.warnings == []
    assert result.debug == {}

def test_retrieved_chunk_scores_default_none_and_sources_empty() -> None:
    chunk = RetrievedChunk(chunk_id="c-1", text="t", metadata={}, heading_path=[])
    assert chunk.vector_score is None
    assert chunk.graph_score is None
    assert chunk.rrf_score is None
    assert chunk.rerank_score is None
    assert chunk.sources == []

def test_candidate_keeps_source_and_rank() -> None:
    cand = RetrievalCandidate(chunk_id="c-1", source="vector", rank=3, score=0.5)
    assert cand.source == "vector"
    assert cand.rank == 3

def test_graph_context_dedup_key_entity_uses_norm_name() -> None:
    item = GraphContextItem(
        kind="entity", name="Hồ Chí Minh", norm_name="hồ chí minh", description="d"
    )
    assert item.dedup_key() == ("entity", "hồ chí minh")

def test_graph_context_dedup_key_relation_uses_structured_triple() -> None:
    item = GraphContextItem(
        kind="relation",
        source_name="Phan Bội Châu",
        source_norm="phan bội châu",
        target_name="Cường Để",
        target_norm="cường để",
        keyword="ủng hộ",
        description="d",
    )
    assert item.dedup_key() == ("relation", "phan bội châu", "ủng hộ", "cường để")

def test_backend_error_carries_code() -> None:
    err = RetrievalBackendError("qdrant_unavailable")
    assert err.code == "qdrant_unavailable"
    assert isinstance(err, Exception)

def test_config_has_retrieval_knobs_with_expected_defaults() -> None:
    s = get_settings()
    assert s.rag_top_k == 20
    assert s.graph_top_k == 20
    assert s.hybrid_candidate_k == 30
    assert s.rerank_top_k == 8
    assert s.hybrid_rrf_k == 60
    # reranker_model có thể được .env bật (env-configurable) -> chỉ kiểm knob tồn tại + kiểu.
    assert isinstance(s.reranker_model, str)
    assert s.graph_max_seed_entities == 5
    assert s.graph_max_chunks_per_seed == 20
    assert s.graph_hub_source_count_threshold == 80
    assert s.graph_max_context_items == 12
    # Knob mới Phase 2/3/4 (không set trong .env -> giữ default).
    assert s.graph_max_path_hops == 3
    assert s.graph_path_hit_weight == 1.5
    assert s.bm25_model == "Qdrant/bm25"
    assert s.bm25_top_k == 20
    assert s.sparse_vector_name == "bm25"
