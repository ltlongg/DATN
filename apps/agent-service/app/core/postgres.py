"""Connection pool Postgres dùng chung cho hot path ONLINE của agent-service.

Trước đây mỗi store (`chunk_store`, `event_store`, `gazetteer_store`, `usage_log`) tự
`psycopg.connect()` mỗi lần gọi. Một câu `/ask` chạm Postgres nhiều lần (hydrate chunk +
timeline events + gazetteer + 3 lần ghi `llm_usage`) -> mở/đóng nhiều connection tới DB
REMOTE, mỗi lần cõng round-trip TCP+auth. Pool giữ sẵn connection để tái dùng.

`connection()` giữ nguyên hợp đồng cũ của các store: context manager, `row_factory=dict_row`,
commit khi thoát sạch / rollback khi có exception — chỉ khác connection được TRẢ lại pool
thay vì đóng hẳn. Truyền `database_url` khác cấu hình (test/script) -> bỏ pool, connect
trực tiếp (pool gắn 1 conninfo cố định).

Vòng đời: `get_pool()` mở lazy lần đầu (server: warm qua lifespan main.py; CLI offline: lazy
+ atexit đóng). `close_pool()` idempotent. Chỉ dùng cho ĐỌC online + ghi usage; đường ghi
bulk offline (`upsert_*`, `replace_timeline_events`) vẫn `psycopg.connect` trực tiếp vì chạy
một lần trong script, không hưởng lợi từ pool.
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

__all__ = ["connection", "get_pool", "close_pool", "DictConnection"]

DictConnection = Connection[dict[str, Any]]


def _database_url(database_url: str | None = None) -> str:
    url = database_url or get_settings().database_url
    if not url:
        raise RuntimeError("Thiếu DATABASE_URL trong .env để kết nối Postgres.")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


_pool: ConnectionPool[DictConnection] | None = None


def get_pool() -> ConnectionPool[DictConnection]:
    """Trả pool đang mở, tạo lần đầu nếu chưa có. `open()` không blocking."""
    global _pool
    if _pool is None:
        settings = get_settings()
        pool: ConnectionPool[DictConnection] = ConnectionPool(
            conninfo=_database_url(),
            min_size=settings.pg_pool_min_size,
            max_size=settings.pg_pool_max_size,
            kwargs={"row_factory": dict_row},
            open=False,
            name="agent-pg",
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

    Mặc định lấy từ pool. `database_url` khác cấu hình -> mở trực tiếp (bỏ pool).
    """
    if database_url is not None and _database_url(database_url) != _database_url():
        with psycopg.connect(_database_url(database_url), row_factory=dict_row) as conn:
            yield conn
        return
    with get_pool().connection() as conn:
        yield conn
