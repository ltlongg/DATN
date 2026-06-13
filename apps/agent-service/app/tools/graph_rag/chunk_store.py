"""Postgres source of truth cho chunks + full metadata."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from app.core.config import get_settings

CREATE_RAG_CHUNKS_SQL = """
CREATE TABLE IF NOT EXISTS rag_chunks (
    chunk_id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    embedding_text TEXT NOT NULL,
    metadata JSONB NOT NULL,
    heading_path TEXT[] NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

CREATE_INDEX_SQLS = [
    """
    CREATE INDEX IF NOT EXISTS rag_chunks_heading_path_gin_idx
    ON rag_chunks USING GIN (heading_path);
    """,
    # times/actors/locations/events không còn là cột riêng — chúng nằm trong `metadata`
    # JSONB; query GIN trên metadata vẫn lọc được (vd metadata @> '{"actors":[...]}').
    "CREATE INDEX IF NOT EXISTS rag_chunks_metadata_gin_idx ON rag_chunks USING GIN (metadata);",
]

UPSERT_RAG_CHUNK_SQL = """
INSERT INTO rag_chunks (
    chunk_id,
    text,
    embedding_text,
    metadata,
    heading_path
) VALUES (
    %s, %s, %s, %s::jsonb, %s::text[]
)
ON CONFLICT (chunk_id) DO UPDATE SET
    text = EXCLUDED.text,
    embedding_text = EXCLUDED.embedding_text,
    metadata = EXCLUDED.metadata,
    heading_path = EXCLUDED.heading_path,
    updated_at = now();
"""


def _database_url(database_url: str | None = None) -> str:
    url = database_url or get_settings().database_url
    if not url:
        raise RuntimeError("Thiếu DATABASE_URL trong .env để ghi rag_chunks.")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _record_params(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["chunk_id"],
        record["text"],
        record["embedding_text"],
        Jsonb(record["metadata"]),
        record.get("heading_path") or [],
    )


def ensure_rag_chunks_table(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(CREATE_RAG_CHUNKS_SQL)
        for sql in CREATE_INDEX_SQLS:
            cur.execute(sql)


def upsert_rag_chunks(
    records: Iterable[dict[str, Any]], database_url: str | None = None
) -> int:
    """Tạo bảng nếu cần và upsert chunks vào Postgres."""
    rows = list(records)
    if not rows:
        return 0

    with psycopg.connect(_database_url(database_url)) as conn:
        ensure_rag_chunks_table(conn)
        with conn.cursor() as cur:
            cur.executemany(UPSERT_RAG_CHUNK_SQL, [_record_params(row) for row in rows])
        conn.commit()
    return len(rows)


def get_rag_chunks_by_ids(
    chunk_ids: list[str], database_url: str | None = None
) -> list[dict[str, Any]]:
    """Lấy full chunk rows theo `chunk_id`, phục vụ retrieval join."""
    if not chunk_ids:
        return []

    with psycopg.connect(_database_url(database_url), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM rag_chunks
                WHERE chunk_id = ANY(%s::text[])
                ORDER BY array_position(%s::text[], chunk_id)
                """,
                (chunk_ids, chunk_ids),
            )
            return list(cur.fetchall())
