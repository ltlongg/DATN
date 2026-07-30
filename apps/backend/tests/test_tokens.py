"""Item 3 — token theo hội thoại/message: token_service thuần (không DB) + endpoint (llm_usage
thật, cô lập bằng ngày cũ 2020). UndefinedTable -> [] dùng chung code với cost (test_cost.py)."""

from __future__ import annotations

import uuid

import psycopg

from app.services.token_service import build_message_tokens, compute_token_summary

# Khoảng ngày cũ để cô lập usage của test khỏi usage thật.
_FROM, _TO = "2020-01-01", "2020-01-03"

# DDL đầy đủ (kèm cột mới) + ALTER phòng bảng đã tồn tại từ schema cũ chỉ có user_id.
_DDL = """
CREATE TABLE IF NOT EXISTS llm_usage (
    id                UUID PRIMARY KEY,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    task              TEXT NOT NULL,
    model             TEXT NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    user_id           TEXT,
    conversation_id   TEXT,
    message_id        TEXT
);
"""
_ALTERS = (
    "ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS conversation_id TEXT;",
    "ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS message_id TEXT;",
)


def _ensure_table(conn: psycopg.Connection) -> None:  # type: ignore[type-arg]
    with conn.cursor() as cur:
        cur.execute(_DDL)
        for sql in _ALTERS:
            cur.execute(sql)


def _insert(conn, task, tokens, *, created_at, conversation_id=None, message_id=None,  # type: ignore[no-untyped-def]
            prompt=0, completion=0, model="m") -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO llm_usage (id, created_at, task, model, prompt_tokens, "
            "completion_tokens, total_tokens, conversation_id, message_id) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (str(uuid.uuid4()), created_at, task, model, prompt, completion, tokens,
             conversation_id, message_id),
        )


# --- compute_token_summary --------------------------------------------------


def test_token_summary_empty() -> None:
    s = compute_token_summary([])
    assert s.overall.total_calls == 0
    assert s.overall.total_tokens == 0
    assert s.overall.avg_tokens_per_call == 0.0
    assert s.by_conversation == []


def test_token_summary_aggregates_overall_and_by_conversation() -> None:
    rows = [
        {"conversation_id": "c1", "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        {"conversation_id": "c1", "prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
        {"conversation_id": "c2", "prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    ]
    s = compute_token_summary(rows)
    assert s.overall.total_calls == 3
    assert s.overall.total_prompt_tokens == 31
    assert s.overall.total_completion_tokens == 16
    assert s.overall.total_tokens == 47
    assert s.overall.avg_tokens_per_call == round(47 / 3, 2)

    by_id = {c.conversation_id: c for c in s.by_conversation}
    assert by_id["c1"].call_count == 2
    assert by_id["c1"].total_tokens == 45
    assert by_id["c2"].call_count == 1
    assert by_id["c2"].total_tokens == 2


# --- build_message_tokens ---------------------------------------------------


def test_build_message_tokens_groups_by_message_and_sums() -> None:
    rows = [
        {"message_id": "m1", "task": "build_query", "model": "gpt-a",
         "prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
        {"message_id": "m1", "task": "synthesize", "model": "gpt-a",
         "prompt_tokens": 30, "completion_tokens": 20, "total_tokens": 50},
        {"message_id": "m1", "task": "guardrail_input", "model": "gpt-guard",
         "prompt_tokens": 5, "completion_tokens": 1, "total_tokens": 6},
    ]
    result = build_message_tokens(rows)
    assert len(result) == 1
    msg = result[0]
    assert msg.message_id == "m1"
    assert msg.total_tokens == 68
    # 3 task, model gắn Ở TỪNG dòng (guardrail dùng model khác).
    tasks = {r.task: r for r in msg.rows}
    assert set(tasks) == {"build_query", "synthesize", "guardrail_input"}
    assert tasks["guardrail_input"].model == "gpt-guard"
    assert tasks["synthesize"].total_tokens == 50


def test_build_message_tokens_empty() -> None:
    assert build_message_tokens([]) == []


# --- endpoints (DB thật) ----------------------------------------------------


def test_token_summary_endpoint_excludes_null_conversation(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _ensure_table(db_conn)
    _insert(db_conn, "build_query", 15, created_at="2020-01-01 10:00",
            conversation_id="conv-A", message_id="m1", prompt=10, completion=5)
    _insert(db_conn, "synthesize", 40, created_at="2020-01-02 10:00",
            conversation_id="conv-A", message_id="m1", prompt=30, completion=10)
    # Row usage cũ KHÔNG gắn conversation_id -> KHÔNG tính vào card/by_conversation.
    _insert(db_conn, "synthesize", 999, created_at="2020-01-02 11:00")

    r = client.get(
        "/api/admin/logs/token-summary",
        params={"from_date": _FROM, "to_date": _TO},
        headers=auth("admin"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["overall"]["total_calls"] == 2  # row NULL bị loại
    assert body["overall"]["total_tokens"] == 55
    by_conv = {c["conversation_id"]: c for c in body["by_conversation"]}
    assert by_conv["conv-A"]["call_count"] == 2
    assert by_conv["conv-A"]["total_tokens"] == 55


def test_conversation_tokens_endpoint_breakdown_by_task(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _ensure_table(db_conn)
    _insert(db_conn, "guardrail_input", 6, created_at="2020-01-01 10:00",
            conversation_id="conv-B", message_id="msg-1", model="gpt-guard", prompt=5, completion=1)
    _insert(db_conn, "build_query", 12, created_at="2020-01-01 10:00",
            conversation_id="conv-B", message_id="msg-1", model="gpt-a", prompt=10, completion=2)
    _insert(db_conn, "synthesize", 50, created_at="2020-01-01 10:00",
            conversation_id="conv-B", message_id="msg-1", model="gpt-a", prompt=30, completion=20)

    r = client.get("/api/admin/logs/conversations/conv-B/tokens", headers=auth("admin"))
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    msg = body[0]
    assert msg["message_id"] == "msg-1"
    assert msg["total_tokens"] == 68
    tasks = {row["task"]: row for row in msg["rows"]}
    assert set(tasks) == {"guardrail_input", "build_query", "synthesize"}
    assert tasks["guardrail_input"]["model"] == "gpt-guard"  # model ở TỪNG task


def test_token_summary_requires_admin(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/admin/logs/token-summary", headers=auth("user"))
    assert r.status_code == 403
