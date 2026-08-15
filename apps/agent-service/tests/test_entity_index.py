"""Test entity_index: grounding qua resolve() (giữ dấu) và cache version (rebuild khi
alias_map/KG đổi).

Tất cả in-memory / fake driver — không chạm Neo4j thật (chính là điều grounding phải
đạt: tra inverted-index, KHÔNG bắn Cypher exact-match từng cụm).
"""

from __future__ import annotations

import json

from app.indexing.graph.normalize import normalize_name
from app.tools.graph_rag import entity_index as EI
from app.tools.graph_rag.entity_index import EntityIndex

def _index(entities):
    return EntityIndex.from_entities(
        entities, alias_map_version="a", kg_version="k"
    )

# --- Grounding (bước B) ---------------------------------------------------

def test_ground_returns_entity_when_norm_name_in_kg() -> None:
    idx = _index([{"name": "Trương Định", "norm_name": "trương định", "source_count": 5}])
    got = idx.ground("Trương Định")
    assert got is not None
    assert got.norm_name == "trương định"
    assert got.source_count == 5

def test_ground_returns_none_when_entity_not_in_kg() -> None:
    idx = _index([{"name": "Trương Định", "norm_name": "trương định", "source_count": 5}])
    assert idx.ground("Phan Bội Châu") is None

def test_grounding_resolves_alias_on_accented_mention(monkeypatch) -> None:
    # "Nguyễn Ái Quốc" là alias của "Hồ Chí Minh" -> ground phải đi qua resolve() và
    # ra đúng canonical CÓ DẤU "hồ chí minh".
    monkeypatch.setattr(
        EI,
        "resolve",
        lambda m: ("Hồ Chí Minh", "hồ chí minh")
        if "Quốc" in m
        else (m, normalize_name(m)),
    )
    idx = _index([{"name": "Hồ Chí Minh", "norm_name": "hồ chí minh", "source_count": 9}])
    got = idx.ground("Nguyễn Ái Quốc")
    assert got is not None
    assert got.norm_name == "hồ chí minh"
    assert got.name == "Hồ Chí Minh"

def test_grounding_uses_inverted_index_not_per_phrase_cypher() -> None:
    # ground() chỉ tra dict in-memory: index dựng KHÔNG có driver nào, vẫn ground được
    # -> chứng tỏ không bắn Cypher exact-match cho từng cụm.
    idx = _index([{"name": "Đà Nẵng", "norm_name": "đà nẵng", "source_count": 3}])
    assert idx.ground("đà nẵng").norm_name == "đà nẵng"

# --- Build từ Neo4j (fake driver) ----------------------------------------

class _FakeSession:
    def __init__(self, rows):
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, cypher, **kwargs):
        return list(self._rows)

class _FakeDriver:
    def __init__(self, rows):
        self._rows = rows

    def session(self):
        return _FakeSession(self._rows)

def test_build_entity_index_maps_neo4j_rows(monkeypatch) -> None:
    rows = [{"name": "Trương Định", "norm_name": "trương định", "source_count": 5}]
    monkeypatch.setattr(
        EI, "_current_versions", lambda driver=None: {"alias_map_version": "a", "kg_version": "k"}
    )
    idx = EI.build_entity_index(driver=_FakeDriver(rows))
    got = idx.ground("Trương Định")
    assert got is not None and got.source_count == 5

# --- Cache version --------------------------------------------------------

def test_entity_index_rebuilds_when_alias_or_kg_version_changes(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "entity_index.json"
    cache.write_text(
        json.dumps({"alias_map_version": "OLD", "kg_version": "OLD", "entities": []}),
        encoding="utf-8",
    )
    built = {"n": 0}

    def fake_build(driver=None):
        built["n"] += 1
        return EntityIndex.from_entities(
            [{"name": "X", "norm_name": "x", "source_count": 1}],
            alias_map_version="NEW",
            kg_version="NEW",
        )

    monkeypatch.setattr(EI, "build_entity_index", fake_build)
    monkeypatch.setattr(
        EI, "_current_versions", lambda driver=None: {"alias_map_version": "NEW", "kg_version": "NEW"}
    )
    idx = EI.load_entity_index(driver=object(), cache_path=cache)

    assert built["n"] == 1  # đã rebuild
    assert idx.ground("X") is not None
    data = json.loads(cache.read_text(encoding="utf-8"))
    assert data["alias_map_version"] == "NEW" and data["kg_version"] == "NEW"  # cache mới

def test_entity_index_loads_from_cache_when_versions_match(tmp_path, monkeypatch) -> None:
    cache = tmp_path / "entity_index.json"
    cache.write_text(
        json.dumps(
            {
                "alias_map_version": "V",
                "kg_version": "V",
                "entities": [{"name": "Y", "norm_name": "y", "source_count": 2}],
            }
        ),
        encoding="utf-8",
    )

    def fake_build(driver=None):
        raise AssertionError("không được rebuild khi version khớp")

    monkeypatch.setattr(EI, "build_entity_index", fake_build)
    monkeypatch.setattr(
        EI, "_current_versions", lambda driver=None: {"alias_map_version": "V", "kg_version": "V"}
    )
    idx = EI.load_entity_index(driver=object(), cache_path=cache)
    assert idx.ground("Y") is not None
