"""Module 4 — Chi phí: cost_service thuần (không DB) + endpoints (llm_usage thật, cô lập
bằng ngày cũ 2020 để không lẫn usage thật) + regression bảng chưa tồn tại -> 200 rỗng.
"""

from __future__ import annotations

import uuid

import psycopg

from app.services.cost_service import (
    compute_cost_by_day,
    compute_cost_by_task,
    compute_cost_overview,
)

# Khoảng ngày cũ để cô lập usage của test khỏi usage thật (nếu có).
_FROM, _TO = "2020-01-01", "2020-01-03"

_DDL = """
CREATE TABLE IF NOT EXISTS llm_usage (
    id                UUID PRIMARY KEY,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    task              TEXT NOT NULL,
    model             TEXT NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    user_id           TEXT
);
"""


def _ensure_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(_DDL)


def _insert(conn, task, tokens, *, created_at, user_id=None, prompt=0, completion=0):  # type: ignore[no-untyped-def]
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO llm_usage (id, created_at, task, model, prompt_tokens, "
            "completion_tokens, total_tokens, user_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (str(uuid.uuid4()), created_at, task, "m", prompt, completion, tokens, user_id),
        )


# --- pure cost_service ------------------------------------------------------


def test_compute_cost_overview() -> None:
    rows = [
        {"total_tokens": 10, "prompt_tokens": 6, "completion_tokens": 4},
        {"total_tokens": 20, "prompt_tokens": 15, "completion_tokens": 5},
    ]
    o = compute_cost_overview(rows)
    assert o.total_calls == 2
    assert o.total_tokens == 30
    assert o.total_prompt_tokens == 21
    assert o.avg_tokens_per_call == 15.0


def test_compute_cost_overview_empty() -> None:
    o = compute_cost_overview([])
    assert o.total_calls == 0 and o.total_tokens == 0 and o.avg_tokens_per_call == 0.0


def test_compute_cost_by_day_grouped_sorted() -> None:
    rows = [
        {"created_at": "2020-01-02 10:00:00", "total_tokens": 5},
        {"created_at": "2020-01-01 09:00:00", "total_tokens": 7},
        {"created_at": "2020-01-01 12:00:00", "total_tokens": 3},
    ]
    days = compute_cost_by_day(rows)
    assert [d.day for d in days] == ["2020-01-01", "2020-01-02"]  # sort tăng dần
    assert days[0].calls == 2 and days[0].total_tokens == 10


def test_compute_cost_by_task_grouped() -> None:
    rows = [
        {"task": "build_query", "total_tokens": 4},
        {"task": "synthesize", "total_tokens": 20},
        {"task": "build_query", "total_tokens": 6},
    ]
    tasks = {t.task: t for t in compute_cost_by_task(rows)}
    assert tasks["build_query"].calls == 2 and tasks["build_query"].total_tokens == 10
    assert tasks["synthesize"].total_tokens == 20


# --- endpoints --------------------------------------------------------------


def test_cost_overview_endpoint(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _ensure_table(db_conn)
    _insert(db_conn, "build_query", 15, created_at="2020-01-01 10:00", prompt=10, completion=5)
    _insert(db_conn, "synthesize", 40, created_at="2020-01-02 10:00", prompt=30, completion=10)
    r = client.get(
        "/api/admin/cost/overview",
        params={"from_date": _FROM, "to_date": _TO},
        headers=auth("admin"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total_calls"] == 2
    assert body["total_tokens"] == 55


def test_cost_by_day_and_by_task_endpoints(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _ensure_table(db_conn)
    _insert(db_conn, "build_query", 10, created_at="2020-01-01 10:00")
    _insert(db_conn, "synthesize", 20, created_at="2020-01-02 10:00")
    admin = auth("admin")
    by_day = client.get(
        "/api/admin/cost/by-day", params={"from_date": _FROM, "to_date": _TO}, headers=admin
    ).json()
    assert [d["day"] for d in by_day] == ["2020-01-01", "2020-01-02"]
    by_task = client.get(
        "/api/admin/cost/by-task", params={"from_date": _FROM, "to_date": _TO}, headers=admin
    ).json()
    assert {t["task"] for t in by_task} == {"build_query", "synthesize"}


def test_cost_top_users_join(client, auth, db_conn, users) -> None:  # type: ignore[no-untyped-def]
    _ensure_table(db_conn)
    user = users["user"]
    _insert(db_conn, "synthesize", 100, created_at="2020-01-01 10:00", user_id=user.id)
    r = client.get(
        "/api/admin/cost/top-users",
        params={"from_date": _FROM, "to_date": _TO},
        headers=auth("admin"),
    )
    assert r.status_code == 200
    top = r.json()
    assert top[0]["email"] == "user-test@example.com"
    assert top[0]["total_tokens"] == 100


def test_cost_overview_when_table_missing_returns_empty(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    # Regression: bảng llm_usage chưa tồn tại -> 200 số liệu rỗng, KHÔNG 500.
    with db_conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS llm_usage")
    r = client.get("/api/admin/cost/overview", headers=auth("admin"))
    assert r.status_code == 200
    assert r.json()["total_calls"] == 0


def test_cost_requires_admin(client, auth) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/admin/cost/overview", headers=auth("user")).status_code == 403
