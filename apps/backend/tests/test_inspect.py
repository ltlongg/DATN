"""API test KB Inspector: chunks/events (Postgres thật, cô lập bằng txn rollback + marker
duy nhất để không lẫn ~1213 chunk/event thật), entities (proxy agent mock), gác admin.
"""

from __future__ import annotations

from typing import Any

import psycopg
from psycopg.types.json import Jsonb

# Marker duy nhất -> search chỉ khớp chunk/event của test, count tất định dù DB có data thật.
_CM = "ZZINSPECTCHUNK"
_EM = "ZZINSPECTEVENT"


def _insert_chunk(
    conn: psycopg.Connection,
    chunk_id: str,
    text: str,
    *,
    heading_path: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO rag_chunks (chunk_id, text, embedding_text, metadata, heading_path) "
            "VALUES (%s, %s, %s, %s, %s::text[])",
            (chunk_id, text, text, Jsonb(metadata or {}), heading_path or []),
        )


def _insert_event(
    conn: psycopg.Connection,
    event_id: str,
    label: str,
    *,
    summary: str = "tóm tắt",
    confidence: str = "cao",
    time_start: str | None = None,
    locations: list[str] | None = None,
    source_chunk_ids: list[str] | None = None,
) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO timeline_events (event_id, label, summary, time_start, time_end, "
            "locations, confidence, parent_event_norm, source_chunk_ids) "
            "VALUES (%s, %s, %s, %s, %s, %s::text[], %s, %s, %s::text[])",
            (
                event_id,
                label,
                summary,
                time_start,
                None,
                locations or [],
                confidence,
                None,
                source_chunk_ids or [],
            ),
        )


# --- chunks -----------------------------------------------------------------


def test_list_chunks_search_and_paginate(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _insert_chunk(db_conn, "zz-c-1", f"{_CM} nội dung một", metadata={"chunk_index": 1})
    _insert_chunk(db_conn, "zz-c-2", f"{_CM} nội dung hai", metadata={"chunk_index": 2})
    r = client.get(
        "/api/admin/kb/chunks", params={"q": _CM, "limit": 1}, headers=auth("admin")
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 2  # marker duy nhất -> đúng 2, không lẫn data thật
    assert len(body["items"]) == 1  # limit=1
    assert body["items"][0]["chunk_id"] == "zz-c-1"  # sort theo chunk_index


def test_list_chunks_filter_heading(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _insert_chunk(
        db_conn, "zz-c-h", f"{_CM} có heading", heading_path=["ZZHEAD", "con"]
    )
    r = client.get(
        "/api/admin/kb/chunks",
        params={"q": _CM, "heading": "ZZHEAD"},
        headers=auth("admin"),
    )
    assert r.status_code == 200
    assert [i["chunk_id"] for i in r.json()["items"]] == ["zz-c-h"]


def test_chunk_detail_with_referencing_events(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _insert_chunk(
        db_conn,
        "zz-c-detail",
        f"{_CM} full text",
        metadata={"source_file": "lichsu.clean.md", "start_line": 3, "end_line": 9},
    )
    _insert_event(
        db_conn, "zz-e-ref", f"{_EM} sự kiện", source_chunk_ids=["zz-c-detail"]
    )
    _insert_event(db_conn, "zz-e-other", f"{_EM} khác", source_chunk_ids=["zz-other"])
    r = client.get("/api/admin/kb/chunks/zz-c-detail", headers=auth("admin"))
    assert r.status_code == 200
    body = r.json()
    assert body["text"] == f"{_CM} full text"
    assert body["metadata"]["source_file"] == "lichsu.clean.md"
    # chỉ event tham chiếu đúng chunk (source_chunk_ids @> [chunk_id]).
    assert [e["event_id"] for e in body["referencing_events"]] == ["zz-e-ref"]


def test_chunk_detail_404(client, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/admin/kb/chunks/khong-co", headers=auth("admin"))
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"


# --- events -----------------------------------------------------------------


def test_list_events_search_and_filter_confidence(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _insert_event(db_conn, "zz-e-1", f"{_EM} cao", confidence="cao", time_start="1858")
    _insert_event(db_conn, "zz-e-2", f"{_EM} thấp", confidence="thấp", time_start="1862")
    r = client.get(
        "/api/admin/kb/events",
        params={"q": _EM, "confidence": "cao"},
        headers=auth("admin"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1
    assert body["items"][0]["event_id"] == "zz-e-1"


def test_event_detail(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _insert_event(
        db_conn,
        "zz-e-detail",
        f"{_EM} chi tiết",
        summary="Pháp nổ súng ở Đà Nẵng",
        locations=["Đà Nẵng"],
        source_chunk_ids=["zz-c-a", "zz-c-b"],
    )
    r = client.get("/api/admin/kb/events/zz-e-detail", headers=auth("admin"))
    assert r.status_code == 200
    body = r.json()
    assert body["summary"] == "Pháp nổ súng ở Đà Nẵng"
    assert body["locations"] == ["Đà Nẵng"]
    assert body["source_chunk_ids"] == ["zz-c-a", "zz-c-b"]


def test_event_detail_404(client, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/admin/kb/events/khong-co", headers=auth("admin"))
    assert r.status_code == 404


# --- entities (proxy) -------------------------------------------------------


def test_entities_proxy_forwards_chunk_id(client, auth, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, Any] = {}

    async def fake_agent_get(path, params=None):  # type: ignore[no-untyped-def]
        captured["path"] = path
        captured["params"] = params
        return {"items": [], "total": 0, "limit": 50, "offset": 0}

    monkeypatch.setattr("app.api.inspect.agent_get", fake_agent_get)
    r = client.get(
        "/api/admin/kb/entities", params={"chunk_id": "zz-c-1"}, headers=auth("admin")
    )
    assert r.status_code == 200
    assert captured["path"] == "/kb/entities"
    assert captured["params"]["chunk_id"] == "zz-c-1"


def test_entity_detail_proxy(client, auth, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    async def fake_agent_get(path, params=None):  # type: ignore[no-untyped-def]
        return {"name": "Trương Định", "norm_name": "trương định", "edges": []}

    monkeypatch.setattr("app.api.inspect.agent_get", fake_agent_get)
    r = client.get("/api/admin/kb/entities/trương định", headers=auth("admin"))
    assert r.status_code == 200
    assert r.json()["norm_name"] == "trương định"


# --- gác admin --------------------------------------------------------------


def test_kb_requires_admin(client, auth) -> None:  # type: ignore[no-untyped-def]
    for path in ("/api/admin/kb/chunks", "/api/admin/kb/events", "/api/admin/kb/entities"):
        r = client.get(path, headers=auth("user"))
        assert r.status_code == 403, path
