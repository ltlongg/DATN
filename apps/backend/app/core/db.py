"""Postgres access cho backend — psycopg trực tiếp (KHÔNG ORM), theo đúng pattern
`agent-service/.../chunk_store.py`.

- `_database_url`: strip `+psycopg` khỏi DATABASE_URL (dialect SQLAlchemy) vì
  `psycopg.connect` không hiểu nó.
- `connection()`: context manager cấp 1 connection (row_factory=dict_row) cho mỗi
  request. Mặc định lấy từ `psycopg_pool.ConnectionPool` (giữ sẵn connection để tái
  dùng thay vì mở/đóng mỗi request — DB remote nên round-trip TCP+auth mỗi lần là
  đáng kể). Nếu truyền `database_url` khác cấu hình (test/script one-off) thì bỏ qua
  pool, mở connection trực tiếp. Semantics giống hệt trước: commit khi thoát sạch,
  rollback khi có exception — chỉ khác connection được TRẢ lại pool thay vì đóng hẳn.

Vòng đời pool: `get_pool()` mở lazy lần dùng đầu (server: qua lifespan ở main.py; CLI
script: lazy + `atexit` đóng sạch). `close_pool()` idempotent.
"""

from __future__ import annotations

import atexit
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

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
        id             UUID PRIMARY KEY,
        email          TEXT UNIQUE NOT NULL,
        name           TEXT NOT NULL,
        role           TEXT NOT NULL,
        password_hash  TEXT NOT NULL,
        is_active      BOOLEAN NOT NULL DEFAULT true,
        question_quota INTEGER,  -- NULL = không giới hạn
        created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    # is_active/question_quota thêm sau khi bảng users đã tồn tại ở dev DB dùng chung — CREATE
    # TABLE IF NOT EXISTS ở trên không tự thêm cột vào bảng cũ. ADD COLUMN IF NOT EXISTS
    # idempotent, không phá dữ liệu conversations/messages hiện có (xem backend-additions-plan
    # §3.2: dùng ADD COLUMN thay vì drop+recreate để giữ dev data đã có).
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT true;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS question_quota INTEGER;",
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
    # activity_log — mỗi request /api/* ghi 1 dòng (ActivityLogMiddleware). Theo dõi hoạt
    # động hệ thống ở mức endpoint: phần nào OK/lỗi, mất bao lâu, lỗi gì. clock_timestamp()
    # (KHÔNG now()) để nhiều dòng ghi gần nhau giữ đúng thứ tự — cùng lý do bảng messages.
    # KHÔNG index trên path: filter path dùng ILIKE '%...%' nên btree vô dụng (xem
    # activity-log-plan.md §3). Xem activity-log-plan.md để biết toàn bộ thiết kế.
    """
    CREATE TABLE IF NOT EXISTS activity_log (
        id          UUID PRIMARY KEY,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        request_id  TEXT,
        user_id     TEXT,
        method      TEXT NOT NULL,
        path        TEXT NOT NULL,
        status_code INTEGER NOT NULL,
        severity    TEXT NOT NULL,
        latency_ms  INTEGER,
        error       TEXT
    );
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_activity_log_created_at
    ON activity_log (created_at DESC);
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_activity_log_severity
    ON activity_log (severity);
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


# Pool singleton mức module. Mở lazy để import db.py không cần DB sống (test patch
# `connection` nên không bao giờ chạm pool; CLI script mở lazy rồi atexit đóng).
_pool: ConnectionPool[DictConnection] | None = None


def get_pool() -> ConnectionPool[DictConnection]:
    """Trả pool đang mở, tạo lần đầu nếu chưa có. `open()` không blocking — nếu DB tạm
    thời chưa sẵn sàng, pool tự lấp connection ngầm, không làm chết startup."""
    global _pool
    if _pool is None:
        settings = get_settings()
        pool: ConnectionPool[DictConnection] = ConnectionPool(
            conninfo=_database_url(),
            min_size=settings.pg_pool_min_size,
            max_size=settings.pg_pool_max_size,
            kwargs={"row_factory": dict_row},
            open=False,
            name="backend-pg",
        )
        pool.open()
        _pool = pool
        atexit.register(close_pool)
    return _pool


def close_pool() -> None:
    """Đóng pool (idempotent). Gọi lúc shutdown server (lifespan) và atexit cho CLI."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def connection(database_url: str | None = None) -> Iterator[DictConnection]:
    """Cấp 1 connection dict_row; commit khi thoát sạch, rollback nếu có exception.

    Mặc định lấy từ pool. `database_url` khác cấu hình -> mở trực tiếp (bỏ pool) vì pool
    gắn 1 conninfo cố định.
    """
    if database_url is not None and _database_url(database_url) != _database_url():
        with psycopg.connect(_database_url(database_url), row_factory=dict_row) as conn:
            yield conn
        return
    with get_pool().connection() as conn:
        yield conn


def check_connection(database_url: str | None = None) -> bool:
    """Ping Postgres bằng `SELECT 1` cho endpoint /ready. Trả False nếu không kết nối được."""
    try:
        with connection(database_url) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")
            return cur.fetchone() is not None
    except Exception:
        return False
