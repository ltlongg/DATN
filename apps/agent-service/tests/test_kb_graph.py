"""Test read-side graph_store cho KB Inspector: list/count/get entity (fake Neo4j driver)
+ endpoint /kb/entities* (monkeypatch graph_store).

Fake driver không chạy Cypher thật — kiểm việc TRUYỀN THAM SỐ (chunk_id forward) + MAP
kết quả (edges lọc null, neighbor suy ra, hướng cạnh giữ nguyên).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import kb as kb_module
from app.main import app
from app.tools.graph_rag import graph_store as G


class _Result:
    def __init__(self, records):
        self._records = records

    def single(self):
        return self._records[0] if self._records else None

    def __iter__(self):
        return iter(self._records)


class _Session:
    def __init__(self, records, calls):
        self._records = records
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def run(self, cypher, **kwargs):
        self._calls.append(kwargs)
        return _Result(self._records)


class _Driver:
    def __init__(self, records):
        self._records = records
        self.calls: list[dict] = []

    def session(self):
        return _Session(self._records, self.calls)


# --- list / count -----------------------------------------------------------


def test_list_entities_maps_rows() -> None:
    driver = _Driver(
        [
            {
                "name": "Trương Định",
                "norm_name": "trương định",
                "type": "person",
                "description_count": 3,
                "source_chunk_count": 5,
            },
            {
                "name": "Quân Pháp",
                "norm_name": "quân pháp",
                "type": "organization",
                "description_count": 1,
                "source_chunk_count": 9,
            },
        ]
    )
    rows = G.list_entities(limit=50, offset=0, driver=driver)
    assert [r["norm_name"] for r in rows] == ["trương định", "quân pháp"]
    assert rows[0]["description_count"] == 3
    assert rows[0]["source_chunk_count"] == 5


def test_list_entities_forwards_chunk_id_filter() -> None:
    driver = _Driver([])
    G.list_entities(chunk_id="c-42", limit=10, offset=0, driver=driver)
    assert driver.calls[0]["chunk_id"] == "c-42"
    # q/type rỗng -> None (bỏ filter) chứ không phải "" (tránh CONTAINS chuỗi rỗng).
    assert driver.calls[0]["q"] is None and driver.calls[0]["type"] is None


def test_count_entities() -> None:
    assert G.count_entities(driver=_Driver([{"total": 7}])) == 7
    assert G.count_entities(driver=_Driver([])) == 0


# --- get (ego-graph) --------------------------------------------------------


def _entity_record():
    return {
        "name": "Trương Định",
        "norm_name": "trương định",
        "type": "person",
        "descriptions": ["thủ lĩnh nghĩa quân"],
        "source_chunk_ids": ["c-1"],
        "edges": [
            None,  # OPTIONAL MATCH rỗng (từ CASE WHEN r IS NULL) -> phải bị loại
            {
                "keyword": "phong chức cho",
                "descriptions": ["Triều đình Huế phong chức cho Trương Định"],
                "source_chunk_ids": ["c-1"],
                "src_name": "Triều đình Huế",
                "src_norm": "triều đình huế",
                "tgt_name": "Trương Định",
                "tgt_norm": "trương định",
                "nb_name": "Triều đình Huế",
                "nb_norm": "triều đình huế",
                "nb_type": "organization",
            },
        ],
    }


def test_get_entity_builds_ego_graph() -> None:
    entity = G.get_entity("trương định", driver=_Driver([_entity_record()]))
    assert entity is not None
    assert entity["name"] == "Trương Định"
    assert entity["descriptions"] == ["thủ lĩnh nghĩa quân"]
    # edges: null bị loại, còn 1; hướng thật giữ nguyên (seed là target, KHÔNG ép làm source).
    assert len(entity["edges"]) == 1
    edge = entity["edges"][0]
    assert edge["source_norm"] == "triều đình huế"
    assert edge["target_norm"] == "trương định"
    assert edge["keyword"] == "phong chức cho"
    # neighbor suy từ nb_* (distinct).
    assert [n["norm_name"] for n in entity["neighbors"]] == ["triều đình huế"]


def test_get_entity_none_when_missing() -> None:
    assert G.get_entity("không tồn tại", driver=_Driver([])) is None


# --- endpoint /kb/entities* -------------------------------------------------

_client = TestClient(app)


def test_endpoint_list_entities_empty_state(monkeypatch) -> None:
    monkeypatch.setattr(kb_module.graph_store, "list_entities", lambda **kw: [])
    monkeypatch.setattr(kb_module.graph_store, "count_entities", lambda **kw: 0)
    r = _client.get("/kb/entities")
    assert r.status_code == 200
    body = r.json()
    assert body == {"items": [], "total": 0, "limit": 50, "offset": 0}


def test_endpoint_list_entities_shape(monkeypatch) -> None:
    monkeypatch.setattr(
        kb_module.graph_store,
        "list_entities",
        lambda **kw: [
            {
                "name": "Trương Định",
                "norm_name": "trương định",
                "type": "person",
                "description_count": 2,
                "source_chunk_count": 4,
            }
        ],
    )
    monkeypatch.setattr(kb_module.graph_store, "count_entities", lambda **kw: 1)
    r = _client.get("/kb/entities", params={"q": "Trương"})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["norm_name"] == "trương định"


def test_endpoint_get_entity_404(monkeypatch) -> None:
    monkeypatch.setattr(kb_module.graph_store, "get_entity", lambda norm_name: None)
    r = _client.get("/kb/entities/khong-ton-tai")
    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "not_found"
