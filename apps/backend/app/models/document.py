"""Data access cho `documents` (mock metadata, chưa upload file thật) — psycopg trực tiếp."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.core.db import connection

_COLS = "id, name, type, status, chunk_count, created_at, updated_at"


class Document(BaseModel):
    id: str
    name: str
    type: str
    status: str
    chunk_count: int
    created_at: datetime
    updated_at: datetime


def _to_document(row: dict[str, Any]) -> Document:
    return Document(
        id=str(row["id"]),
        name=row["name"],
        type=row["type"],
        status=row["status"],
        chunk_count=row["chunk_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_document(name: str, type_: str, status: str, chunk_count: int) -> Document:
    doc_id = str(uuid.uuid4())
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO documents (id, name, type, status, chunk_count) "
            f"VALUES (%s, %s, %s, %s, %s) RETURNING {_COLS}",
            (doc_id, name, type_, status, chunk_count),
        )
        row = cur.fetchone()
        conn.commit()
    assert row is not None
    return _to_document(row)


def list_documents() -> list[Document]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {_COLS} FROM documents ORDER BY created_at DESC")
        rows = cur.fetchall()
    return [_to_document(r) for r in rows]


def get_document(document_id: str) -> Document | None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {_COLS} FROM documents WHERE id = %s", (document_id,))
        row = cur.fetchone()
    return _to_document(row) if row else None


def update_document(document_id: str, fields: dict[str, Any]) -> Document | None:
    """Cập nhật một phần (PATCH). `fields` chỉ chứa cột hợp lệ đã lọc ở schema/API."""
    if not fields:
        return get_document(document_id)
    set_clause = ", ".join(f"{col} = %s" for col in fields)
    params = [*fields.values(), document_id]
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE documents SET {set_clause}, updated_at = now() WHERE id = %s "
            f"RETURNING {_COLS}",
            params,
        )
        row = cur.fetchone()
        conn.commit()
    return _to_document(row) if row else None


def delete_document(document_id: str) -> bool:
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
        deleted = cur.rowcount > 0
        conn.commit()
    return deleted
