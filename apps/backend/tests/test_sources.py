"""API test xem nguồn trong chat: GET /api/chat/sources/{chunk_id}.

Postgres thật, cô lập bằng txn rollback (fixture `db_conn`). Khác `/api/admin/kb/*`: route
này CHỈ cần đăng nhập — teacher phải gọi được. Xem docs/plan/citation-viewer-plan.md §4.
"""

from __future__ import annotations

import psycopg
from fastapi.testclient import TestClient
from psycopg.types.json import Jsonb


def _insert_chunk(conn: psycopg.Connection, chunk_id: str) -> None:
    text = "Nghĩa quân Bãi Sậy lập căn cứ ở vùng đầm lầy Hưng Yên."
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO rag_chunks (chunk_id, text, embedding_text, metadata, heading_path) "
            "VALUES (%s, %s, %s, %s, %s::text[])",
            (
                chunk_id,
                text,
                text,
                Jsonb(
                    {
                        "source_file": "lichsu.clean.md",
                        "chunk_index": 7,
                        "start_line": 375,
                        "end_line": 378,
                    }
                ),
                ["Thời kì thuộc địa", "Phong trào Cần vương", "Khởi nghĩa Bãi Sậy"],
            ),
        )


def test_teacher_reads_source_full_text(client: TestClient, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _insert_chunk(db_conn, "zz-src-1")
    r = client.get("/api/chat/sources/zz-src-1", headers=auth("teacher"))
    assert r.status_code == 200
    body = r.json()
    assert body["chunk_id"] == "zz-src-1"
    assert body["text"].startswith("Nghĩa quân Bãi Sậy")
    assert body["heading_path"][-1] == "Khởi nghĩa Bãi Sậy"
    # Số dòng đi kèm để modal hiện provenance (danh sách nguồn thì không in).
    assert (body["start_line"], body["end_line"]) == (375, 378)
    # Payload đúng những gì modal hiện: không tên file, không chunk_index, không
    # referencing_events (KB Inspector mới cần).
    assert set(body) == {"chunk_id", "text", "heading_path", "start_line", "end_line"}


def test_admin_reads_source_too(client: TestClient, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _insert_chunk(db_conn, "zz-src-admin")
    r = client.get("/api/chat/sources/zz-src-admin", headers=auth("admin"))
    assert r.status_code == 200


def test_unknown_chunk_returns_404(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/chat/sources/khong-ton-tai", headers=auth("teacher"))
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"


def test_requires_auth(client: TestClient) -> None:
    assert client.get("/api/chat/sources/zz-src-1").status_code == 401


def test_kb_inspector_still_admin_only(client: TestClient, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    """Mở đường xem nguồn cho teacher KHÔNG được nới lỏng router admin."""
    _insert_chunk(db_conn, "zz-src-guard")
    assert (
        client.get("/api/admin/kb/chunks/zz-src-guard", headers=auth("teacher")).status_code
        == 403
    )
