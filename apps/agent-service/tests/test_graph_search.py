"""Test graph_store query-side: match_seed_entities (ground + hub guard) và
search_graph (candidate provenance + graph_context content, relation có cấu trúc).

Fake Neo4j driver/session — không chạm backend thật.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.tools.graph_rag import graph_store as G
from app.tools.graph_rag.entity_index import EntityIndex


def _index(entities):
    return EntityIndex.from_entities(entities, alias_map_version="a", kg_version="k")


class _Result:
    def __init__(self, record):
        self._record = record

    def single(self):
        return self._record


class _Session:
    """Fake session: route 1-hop expand (kwarg norm_name) vs path query (kwargs a,b)."""

    def __init__(self, records_by_norm, paths_by_pair=None):
        self._records = records_by_norm
        self._paths = paths_by_pair or {}
        self.path_calls = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, cypher, **kwargs):
        if "a" in kwargs and "b" in kwargs:  # shortestPath giữa cặp seed
            self.path_calls += 1
            return _Result(self._paths.get(frozenset({kwargs["a"], kwargs["b"]})))
        return _Result(self._records.get(kwargs.get("norm_name")))


class _Driver:
    def __init__(self, records_by_norm, paths_by_pair=None):
        # search_graph mở MỘT session (with) -> giữ 1 instance để test soi path_calls.
        self.session_obj = _Session(records_by_norm, paths_by_pair)

    def session(self):
        return self.session_obj


# --- match_seed_entities --------------------------------------------------


def test_match_seed_entities_grounds_injected_mentions() -> None:
    idx = _index([{"name": "Trương Định", "norm_name": "trương định", "source_count": 3}])
    seeds = G.match_seed_entities("", seed_mentions=["Trương Định"], limit=5, index=idx)
    assert [s.info.norm_name for s in seeds] == ["trương định"]


def test_match_seed_entities_token_match_when_mentions_none() -> None:
    idx = _index([{"name": "Trương Định", "norm_name": "trương định", "source_count": 3}])
    seeds = G.match_seed_entities(
        "vai trò của Trương Định là gì", seed_mentions=None, limit=5, index=idx
    )
    assert [s.info.norm_name for s in seeds] == ["trương định"]


def test_match_seed_entities_drops_single_token_hub_seed() -> None:
    idx = _index([{"name": "Pháp", "norm_name": "pháp", "source_count": 500}])
    seeds = G.match_seed_entities("", seed_mentions=["Pháp"], limit=5, index=idx)
    assert seeds == []  # 1 từ + source_count cao -> hub, bỏ


def test_match_seed_entities_keeps_multiword_even_if_high_count() -> None:
    idx = _index([{"name": "Quân Pháp", "norm_name": "quân pháp", "source_count": 500}])
    seeds = G.match_seed_entities("", seed_mentions=["Quân Pháp"], limit=5, index=idx)
    assert [s.info.norm_name for s in seeds] == ["quân pháp"]


# --- search_graph ---------------------------------------------------------


def _pbc_records():
    return {
        "phan bội châu": {
            "seed_name": "Phan Bội Châu",
            "seed_descriptions": ["nhà cách mạng đầu thế kỷ 20"],
            "seed_chunks": ["c-1", "c-2"],
            "edges": [
                {
                    "keyword": "ủng hộ",
                    "descriptions": ["Phan Bội Châu ủng hộ Cường Để làm minh chủ"],
                    "source_chunk_ids": ["c-2", "c-3"],
                    "src_name": "Phan Bội Châu",
                    "src_norm": "phan bội châu",
                    "tgt_name": "Cường Để",
                    "tgt_norm": "cường để",
                }
            ],
        }
    }


def test_search_graph_returns_candidates_and_graph_context() -> None:
    idx = _index([{"name": "Phan Bội Châu", "norm_name": "phan bội châu", "source_count": 10}])
    cands, ctx = G.search_graph(
        "Phan Bội Châu liên quan gì đến Cường Để?",
        seed_mentions=["Phan Bội Châu"],
        driver=_Driver(_pbc_records()),
        index=idx,
    )
    assert {c.chunk_id for c in cands} == {"c-1", "c-2", "c-3"}
    # c-2 vừa là seed chunk vừa là edge chunk -> điểm cao nhất.
    assert cands[0].chunk_id == "c-2"
    assert all(c.source == "graph" for c in cands)
    assert [c.rank for c in cands] == list(range(1, len(cands) + 1))
    kinds = {i.kind for i in ctx}
    assert kinds == {"entity", "relation"}


def _hue_records():
    # Index: Triều đình Huế -[phong chức cho]-> Trương Định. Seed = Trương Định (TARGET).
    return {
        "trương định": {
            "seed_name": "Trương Định",
            "seed_descriptions": ["thủ lĩnh nghĩa quân"],
            "seed_chunks": ["c-1"],
            "edges": [
                {
                    "keyword": "phong chức cho",
                    "descriptions": ["Triều đình Huế phong chức cho Trương Định"],
                    "source_chunk_ids": ["c-1"],
                    "src_name": "Triều đình Huế",
                    "src_norm": "triều đình huế",
                    "tgt_name": "Trương Định",
                    "tgt_norm": "trương định",
                }
            ],
        }
    }


def test_search_graph_relation_direction_follows_true_edge_not_seed() -> None:
    # Seed là TARGET của cạnh -> KHÔNG được render ngược thành source.
    idx = _index([{"name": "Trương Định", "norm_name": "trương định", "source_count": 5}])
    _, ctx = G.search_graph(
        "ai phong chức cho Trương Định",
        seed_mentions=["Trương Định"],
        driver=_Driver(_hue_records()),
        index=idx,
    )
    rel = next(i for i in ctx if i.kind == "relation")
    assert rel.source_norm == "triều đình huế"  # hướng thật, không phải seed
    assert rel.source_name == "Triều đình Huế"
    assert rel.target_norm == "trương định"
    assert rel.keyword == "phong chức cho"


def test_search_graph_relation_keeps_structured_source_keyword_target() -> None:
    idx = _index([{"name": "Phan Bội Châu", "norm_name": "phan bội châu", "source_count": 10}])
    _, ctx = G.search_graph(
        "x", seed_mentions=["Phan Bội Châu"], driver=_Driver(_pbc_records()), index=idx
    )
    rel = next(i for i in ctx if i.kind == "relation")
    assert rel.source_norm == "phan bội châu"
    assert rel.keyword == "ủng hộ"
    assert rel.target_norm == "cường để"
    assert rel.target_name == "Cường Để"
    assert "Cường Để" in rel.description
    assert rel.source_chunk_ids == ["c-2", "c-3"]  # provenance giữ trên item


def test_search_graph_collects_descriptions_into_context() -> None:
    idx = _index([{"name": "Phan Bội Châu", "norm_name": "phan bội châu", "source_count": 10}])
    _, ctx = G.search_graph(
        "x", seed_mentions=["Phan Bội Châu"], driver=_Driver(_pbc_records()), index=idx
    )
    entity = next(i for i in ctx if i.kind == "entity")
    assert "nhà cách mạng" in entity.description
    assert entity.norm_name == "phan bội châu"
    assert entity.matched_seed == "Phan Bội Châu"


def test_search_graph_empty_when_no_seed() -> None:
    idx = _index([])
    cands, ctx = G.search_graph(
        "câu hỏi không có thực thể nào trong KG",
        seed_mentions=["Thực Thể Lạ"],
        driver=_Driver({}),
        index=idx,
    )
    assert cands == [] and ctx == []


def test_search_graph_caps_chunks_per_seed(monkeypatch) -> None:
    monkeypatch.setattr(
        G,
        "get_settings",
        lambda: SimpleNamespace(
            graph_max_seed_entities=5,
            graph_top_k=20,
            graph_max_chunks_per_seed=1,  # chỉ đếm 1 chunk mỗi seed
            graph_hub_source_count_threshold=80,
            graph_max_context_items=12,
        ),
    )
    idx = _index([{"name": "Phan Bội Châu", "norm_name": "phan bội châu", "source_count": 10}])
    cands, _ = G.search_graph(
        "x", seed_mentions=["Phan Bội Châu"], driver=_Driver(_pbc_records()), index=idx
    )
    assert len(cands) == 1  # cap chặn bùng nổ chunk per seed


# --- C2: path-finding giữa các seed (kích hoạt khi >=2 seed) -----------------


def _two_seed_index():
    return _index(
        [
            {"name": "Phan Bội Châu", "norm_name": "phan bội châu", "source_count": 10},
            {"name": "Phan Châu Trinh", "norm_name": "phan châu trinh", "source_count": 10},
        ]
    )


def _expand_two_seeds():
    # 1-hop của mỗi seed: node cô lập (edges rỗng) -> chỉ có seed chunk, để path là nguồn relation duy nhất.
    return {
        "phan bội châu": {
            "seed_name": "Phan Bội Châu",
            "seed_descriptions": ["nhà cách mạng"],
            "seed_chunks": ["c-1"],
            "edges": [],
        },
        "phan châu trinh": {
            "seed_name": "Phan Châu Trinh",
            "seed_descriptions": ["nhà cải cách"],
            "seed_chunks": ["c-2"],
            "edges": [],
        },
    }


def _path_between_two():
    return {
        frozenset({"phan bội châu", "phan châu trinh"}): {
            "nodes": [
                {"name": "Phan Bội Châu", "norm": "phan bội châu",
                 "descriptions": ["nhà cách mạng"], "chunks": ["c-1"]},
                {"name": "Phan Châu Trinh", "norm": "phan châu trinh",
                 "descriptions": ["nhà cải cách"], "chunks": ["c-2"]},
            ],
            "rels": [
                {"keyword": "cùng thời", "descriptions": ["hai nhà cách mạng cùng thời"],
                 "chunks": ["c-9"], "src_name": "Phan Bội Châu", "src_norm": "phan bội châu",
                 "tgt_name": "Phan Châu Trinh", "tgt_norm": "phan châu trinh"},
            ],
        }
    }


def test_search_graph_pathfinding_two_seeds_links_entities() -> None:
    idx = _two_seed_index()
    cands, ctx = G.search_graph(
        "Quan hệ giữa Phan Bội Châu và Phan Châu Trinh?",
        seed_mentions=["Phan Bội Châu", "Phan Châu Trinh"],
        driver=_Driver(_expand_two_seeds(), _path_between_two()),
        index=idx,
    )
    rels = [i for i in ctx if i.kind == "relation"]
    assert any(
        r.source_norm == "phan bội châu"
        and r.target_norm == "phan châu trinh"
        and r.keyword == "cùng thời"
        for r in rels
    )
    # chunk c-9 nằm trên path -> được score + thành candidate (provenance).
    assert "c-9" in {c.chunk_id for c in cands}


def test_search_graph_no_path_skips_pair() -> None:
    idx = _two_seed_index()
    cands, ctx = G.search_graph(
        "x",
        seed_mentions=["Phan Bội Châu", "Phan Châu Trinh"],
        driver=_Driver(_expand_two_seeds(), {}),  # không có đường nối
        index=idx,
    )
    assert "c-9" not in {c.chunk_id for c in cands}  # không bịa chunk path
    assert not [i for i in ctx if i.kind == "relation"]  # không relation path


def test_search_graph_single_seed_skips_pathfinding() -> None:
    idx = _index([{"name": "Phan Bội Châu", "norm_name": "phan bội châu", "source_count": 10}])
    drv = _Driver(_pbc_records())
    G.search_graph("x", seed_mentions=["Phan Bội Châu"], driver=drv, index=idx)
    assert drv.session_obj.path_calls == 0  # 1 seed -> KHÔNG gọi path cypher


def test_path_cypher_rejects_non_int_maxhop() -> None:
    # Cận var-length nội suy vào chuỗi Cypher -> chỉ chấp nhận int (chặn injection).
    with pytest.raises(AssertionError):
        G._path_cypher("3; DROP")  # type: ignore[arg-type]
