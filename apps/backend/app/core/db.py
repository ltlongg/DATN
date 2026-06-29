"""Postgres access cho backend — psycopg trực tiếp (KHÔNG ORM), theo đúng pattern
`agent-service/.../chunk_store.py`.

- `_database_url`: strip `+psycopg` khỏi DATABASE_URL (dialect SQLAlchemy) vì
  `psycopg.connect` không hiểu nó.
- `connection()`: context manager mở 1 connection (row_factory=dict_row) cho mỗi
  request. MVP quy mô đồ án không cần pool; mỗi handler mở-đóng 1 connection là đủ
  minh bạch và an toàn với code async (chạy qua asyncio.to_thread ở service layer).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row

from app.core.config import get_settings

# Connection trả về dict cho mỗi row (row_factory=dict_row).
DictConnection = Connection[dict[str, Any]]

# DDL nguồn-sự-thật cho 4 bảng backend (CREATE TABLE IF NOT EXISTS — idempotent, KHÔNG
# Alembic; xem backend-plan.md "Công nghệ đề xuất"). Đặt ở đây để cả script init_db.py
# lẫn test fixture cùng dùng một định nghĩa. UUID sinh ở app layer (uuid4) nên không cần
# extension pgcrypto; cột id chỉ là UUID PRIMARY KEY nhận giá trị từ INSERT.
SCHEMA_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS users (
        id            UUID PRIMARY KEY,
        email         TEXT UNIQUE NOT NULL,
        name          TEXT NOT NULL,
        role          TEXT NOT NULL,
        password_hash TEXT NOT NULL,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id         UUID PRIMARY KEY,
        user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        title      TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_conversations_user_updated_at
    ON conversations (user_id, updated_at DESC);
    """,
    """
    CREATE TABLE IF NOT EXISTS messages (
        id                   UUID PRIMARY KEY,
        conversation_id      UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        role                 TEXT NOT NULL,
        content              TEXT NOT NULL,
        clarification_needed BOOLEAN NOT NULL DEFAULT false,
        citations            JSONB NOT NULL DEFAULT '[]',
        visualization        JSONB,
        retrieval_mode       TEXT NOT NULL DEFAULT 'none',
        confidence           TEXT,
        warnings             JSONB NOT NULL DEFAULT '[]',
        -- clock_timestamp() (KHÔNG phải now()): now() trả về thời điểm bắt đầu transaction
        -- nên nhiều message ghi trong cùng 1 txn sẽ trùng created_at -> sai thứ tự
        -- user/assistant. clock_timestamp() tiến theo từng câu lệnh -> thứ tự ổn định.
        created_at           TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_messages_conversation_created_at
    ON messages (conversation_id, created_at);
    """,
    """
    CREATE TABLE IF NOT EXISTS documents (
        id          UUID PRIMARY KEY,
        name        TEXT NOT NULL,
        type        TEXT NOT NULL,
        status      TEXT NOT NULL,
        chunk_count INTEGER NOT NULL DEFAULT 0,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
)


def init_schema(conn: DictConnection) -> None:
    """Chạy toàn bộ DDL (idempotent). Dùng bởi scripts/init_db.py và test fixture."""
    with conn.cursor() as cur:
        for statement in SCHEMA_STATEMENTS:
            cur.execute(statement)
    conn.commit()


def _database_url(database_url: str | None = None) -> str:
    url = database_url or get_settings().database_url
    if not url:
        raise RuntimeError("Thiếu DATABASE_URL trong .env để kết nối Postgres.")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


@contextmanager
def connection(database_url: str | None = None) -> Iterator[DictConnection]:
    """Mở 1 connection dict_row; commit khi thoát sạch, rollback nếu có exception."""
    with psycopg.connect(_database_url(database_url), row_factory=dict_row) as conn:
        yield conn


def check_connection(database_url: str | None = None) -> bool:
    """Ping Postgres bằng `SELECT 1` cho endpoint /ready. Trả False nếu không kết nối được."""
    try:
        with connection(database_url) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() is not None
    except Exception:
        return False
