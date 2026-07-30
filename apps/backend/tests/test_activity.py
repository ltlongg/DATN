"""Activity log: middleware ghi tự động (qua request thật) + endpoint đọc (admin, filter).

Cô lập bằng transaction rollback của fixture db_conn; `app.models.activity` nằm trong
_DB_MODULES nên record_activity ghi vào ĐÚNG connection test (không rò ra Postgres thật).
Mỗi test lọc theo `path` riêng vì fixture `auth` cũng sinh 1 dòng log (POST /api/auth/login).
"""

from __future__ import annotations

import uuid
from typing import Any

import psycopg
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import ActivityLogMiddleware, RequestIDMiddleware


def _rows_for_path(conn: psycopg.Connection, path: str) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT request_id, user_id, method, path, status_code, severity, latency_ms, "
            "error FROM activity_log WHERE path = %s ORDER BY created_at",
            (path,),
        )
        return cur.fetchall()


def _insert(conn: psycopg.Connection, *, path: str, severity: str, status_code: int) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO activity_log (id, method, path, status_code, severity) "
            "VALUES (%s, 'GET', %s, %s, %s)",
            (str(uuid.uuid4()), path, status_code, severity),
        )


# --- middleware ghi log qua request thật ------------------------------------


def test_success_request_logged_ok(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/auth/me", headers=auth("admin"))
    assert r.status_code == 200
    rows = _rows_for_path(db_conn, "/api/auth/me")
    assert len(rows) == 1
    row = rows[0]
    assert row["severity"] == "ok"
    assert row["error"] is None
    assert row["method"] == "GET"
    assert row["latency_ms"] >= 0
    # request_id của dòng log khớp header X-Request-ID trả về.
    assert row["request_id"] == r.headers["X-Request-ID"]


def test_handled_error_logs_error_code(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    # user gọi endpoint admin -> 403 forbidden (AppError handled). Middleware đọc
    # error_code do handler set lên request.state.
    r = client.get("/api/admin/cost/overview", headers=auth("user"))
    assert r.status_code == 403
    rows = _rows_for_path(db_conn, "/api/admin/cost/overview")
    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert rows[0]["error"] == "forbidden"


def test_unhandled_500_logs_exception_type(db_conn) -> None:  # type: ignore[no-untyped-def]
    # App phụ tối giản có route ném exception CHƯA handled -> đi qua nhánh `except` của
    # middleware. Cần raise_server_exceptions=False để TestClient trả 500 thay vì ném lại.
    mini = FastAPI()
    mini.add_middleware(ActivityLogMiddleware)
    mini.add_middleware(RequestIDMiddleware)

    @mini.get("/api/boom")
    def _boom() -> None:
        raise RuntimeError("kaboom")

    with TestClient(mini, raise_server_exceptions=False) as mini_client:
        r = mini_client.get("/api/boom")
    assert r.status_code == 500
    rows = _rows_for_path(db_conn, "/api/boom")
    assert len(rows) == 1
    assert rows[0]["severity"] == "error"
    assert rows[0]["error"].startswith("RuntimeError:")


def test_non_api_path_not_logged(client, db_conn) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/health").status_code == 200
    assert _rows_for_path(db_conn, "/health") == []


def test_user_id_attributed_from_token(client, auth, users, db_conn) -> None:  # type: ignore[no-untyped-def]
    client.get("/api/auth/me", headers=auth("admin"))
    rows = _rows_for_path(db_conn, "/api/auth/me")
    assert rows[0]["user_id"] == users["admin"].id


def test_user_id_null_without_token(client, db_conn) -> None:  # type: ignore[no-untyped-def]
    # Không token -> 401 (handled), user_id NULL vì không có Bearer.
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    rows = _rows_for_path(db_conn, "/api/auth/me")
    assert len(rows) == 1
    assert rows[0]["user_id"] is None
    assert rows[0]["severity"] == "error"


# --- endpoint đọc (admin) ---------------------------------------------------


def test_list_activity_requires_admin(client, auth) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/admin/activity", headers=auth("user")).status_code == 403


def test_list_activity_filter_severity(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _insert(db_conn, path="/api/x/ok-only", severity="ok", status_code=200)
    _insert(db_conn, path="/api/x/err-only", severity="error", status_code=500)
    r = client.get("/api/admin/activity", params={"severity": "error"}, headers=auth("admin"))
    assert r.status_code == 200
    body = r.json()
    paths = {it["path"] for it in body["items"]}
    assert "/api/x/err-only" in paths
    assert "/api/x/ok-only" not in paths
    assert all(it["severity"] == "error" for it in body["items"])


def test_list_activity_filter_path_and_pagination(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    for i in range(3):
        _insert(db_conn, path=f"/api/needle/{i}", severity="ok", status_code=200)
    r = client.get(
        "/api/admin/activity",
        params={"path": "needle", "limit": 2, "offset": 0},
        headers=auth("admin"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 3  # tổng khớp filter, không bị limit
    assert len(body["items"]) == 2  # trang chỉ 2 dòng
    assert all("needle" in it["path"] for it in body["items"])
