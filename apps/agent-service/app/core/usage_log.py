"""Ghi token usage của các lệnh gọi LLM ONLINE (plan, resolve, synthesize) vào Postgres.

Mirror pattern chunk_store.py (`_database_url()` strip +psycopg, CREATE TABLE IF NOT
EXISTS lazy). Bảng `llm_usage` do agent-service sở hữu; backend đọc thẳng (cùng Postgres).

TRIẾT LÝ: ghi usage KHÔNG được làm fail câu trả lời thật (cùng tinh thần build_visualization
— viz lỗi không fail answer). Vì vậy `record_usage` NUỐT mọi exception. Chỉ track lệnh gọi
OpenAI online; KHÔNG track embedding (self-hosted, không tính phí token) hay indexing offline.
Xem backend-additions-plan.md §4.1.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import psycopg

from app.core.postgres import connection

logger = logging.getLogger("agent.usage_log")

CREATE_LLM_USAGE_SQL = """
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

# Bảng đã tồn tại từ trước (chỉ có user_id) -> thêm cột idempotent, GIỮ dữ liệu cũ (llm_usage
# là log rẻ, KHÔNG drop). Row cũ có conversation_id/message_id = NULL (không backfill).
ALTER_LLM_USAGE_SQLS = [
    "ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS conversation_id TEXT;",
    "ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS message_id TEXT;",
]

CREATE_INDEX_SQLS = [
    "CREATE INDEX IF NOT EXISTS llm_usage_created_at_idx ON llm_usage (created_at);",
    "CREATE INDEX IF NOT EXISTS llm_usage_user_id_idx ON llm_usage (user_id);",
    "CREATE INDEX IF NOT EXISTS llm_usage_message_id_idx ON llm_usage (message_id);",
]

INSERT_USAGE_SQL = """
INSERT INTO llm_usage (
    id, task, model, prompt_tokens, completion_tokens, total_tokens,
    user_id, conversation_id, message_id
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
"""


def ensure_llm_usage_table(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(CREATE_LLM_USAGE_SQL)
        for sql in ALTER_LLM_USAGE_SQLS:
            cur.execute(sql)
        for sql in CREATE_INDEX_SQLS:
            cur.execute(sql)


def record_usage(
    task: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    *,
    user_id: str | None = None,
    conversation_id: str | None = None,
    message_id: str | None = None,
    database_url: str | None = None,
) -> None:
    """INSERT 1 dòng usage (tự tạo bảng nếu chưa có). Nuốt MỌI exception — lỗi log usage
    không được làm fail câu trả lời."""
    try:
        with connection(database_url) as conn:
            ensure_llm_usage_table(conn)
            with conn.cursor() as cur:
                cur.execute(
                    INSERT_USAGE_SQL,
                    (
                        str(uuid.uuid4()),
                        task,
                        model,
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                        user_id,
                        conversation_id,
                        message_id,
                    ),
                )
            conn.commit()
    except Exception as exc:  # noqa: BLE001 — ghi usage lỗi không được làm fail answer
        logger.warning("record_usage bỏ qua (task=%s): %s", task, type(exc).__name__)
