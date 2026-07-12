"""Data access cho `documents` — danh mục tài liệu nguồn, psycopg trực tiếp.

KHÔNG còn là metadata mock thuần: mỗi document nối xuống kho tri thức thật qua
`source_file` (khớp `rag_chunks.metadata->>'source_file'`), nên `chunk_count`/`event_count`
được ĐẾM THẬT lúc đọc thay vì lưu số admin gõ tay.

`rag_chunks`/`timeline_events` do agent-service sở hữu DDL nhưng cùng Postgres -> query
thẳng (giống `inspect.py`/`cost.py`). DB chưa index -> bảng chưa tồn tại -> bắt
`UndefinedTable` và coi như kho rỗng (count = 0), tránh 500 thô.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import psycopg
from pydantic import BaseModel

from app.core.db import connection

_COLS = "id, name, type, status, source_file, created_at, updated_at"

# Cột được phép PATCH. `source_file` là KHÓA NỐI -> cố tình KHÔNG cho sửa: đổi nguồn của
# một document = đổi luôn kho chunk nó sở hữu, dễ tạo trạng thái lệch (status 'indexed'
# nhưng trỏ nguồn rỗng). Muốn đổi nguồn thì xoá rồi khai báo lại.
UPDATABLE_COLS = ("name", "type", "status")


class Document(BaseModel):
    id: str
    name: str
    type: str
    status: str
    source_file: str | None = None
    # Đếm thật từ kho (không lưu trong bảng documents).
    chunk_count: int = 0
    event_count: int = 0
    created_at: datetime
    updated_at: datetime


class KbSource(BaseModel):
    """Một nguồn CÓ THẬT trong kho tri thức (`rag_chunks`), kèm document đã khai báo cho
    nó (nếu có). `document_id = None` = chunk trong kho chưa được khai báo ở danh mục."""

    source_file: str
    chunk_count: int
    event_count: int
    document_id: str | None = None


def _to_document(row: dict[str, Any], counts: dict[str, tuple[int, int]]) -> Document:
    chunk_count, event_count = counts.get(row["source_file"] or "", (0, 0))
    return Document(
        id=str(row["id"]),
        name=row["name"],
        type=row["type"],
        status=row["status"],
        source_file=row["source_file"],
        chunk_count=chunk_count,
        event_count=event_count,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def kb_counts() -> dict[str, tuple[int, int]]:
    """`source_file` -> (số chunk, số event) đếm thật từ kho.

    Event của một nguồn = event có `source_chunk_ids` giao với tập chunk_id của nguồn đó
    (toán tử mảng `&&`, cùng cơ chế `builder.py` dùng online). Kho chưa index -> {}.
    """
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                """
                WITH src AS (
                    SELECT metadata->>'source_file' AS source_file,
                           count(*)                 AS chunk_count,
                           array_agg(chunk_id)      AS chunk_ids
                    FROM rag_chunks
                    WHERE metadata->>'source_file' IS NOT NULL
                    GROUP BY 1
                )
                SELECT s.source_file,
                       s.chunk_count,
                       (SELECT count(*) FROM timeline_events e
                        WHERE e.source_chunk_ids && s.chunk_ids) AS event_count
                FROM src s
                """
            )
            rows = cur.fetchall()
    except psycopg.errors.UndefinedTable:
        return {}
    return {r["source_file"]: (int(r["chunk_count"]), int(r["event_count"])) for r in rows}


def list_kb_sources() -> list[KbSource]:
    """Mọi nguồn có thật trong kho + document đang giữ nó. Dùng cho dropdown lọc ở KB
    Chunks (sau `sync_kb_documents` thì `document_id` luôn khác None)."""
    counts = kb_counts()
    if not counts:
        return []
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT id, source_file FROM documents WHERE source_file = ANY(%s::text[])",
            (list(counts),),
        )
        claimed = {r["source_file"]: str(r["id"]) for r in cur.fetchall()}
    return [
        KbSource(
            source_file=source_file,
            chunk_count=chunk_count,
            event_count=event_count,
            document_id=claimed.get(source_file),
        )
        for source_file, (chunk_count, event_count) in sorted(counts.items())
    ]


def sync_kb_documents(source_files: list[str]) -> None:
    """Nguồn đã có chunk trong kho -> TỰ hiện trong danh mục, không bắt admin khai báo.

    Chunk vào kho bằng script indexing offline (không qua UI) nên danh mục luôn có thể
    thiếu. Hàm này lấp phần thiếu: INSERT document cho nguồn chưa có (name = tên file,
    status = 'indexed' vì chunk đã nằm sẵn trong kho). Idempotent nhờ UNIQUE index trên
    `source_file` (partial -> ON CONFLICT phải nhắc lại predicate).
    """
    if not source_files:
        return
    rows = [(str(uuid.uuid4()), sf, sf.rsplit(".", 1)[-1] if "." in sf else "unknown", sf)
            for sf in source_files]
    with connection() as conn, conn.cursor() as cur:
        cur.executemany(
            """
            INSERT INTO documents (id, name, type, status, source_file)
            VALUES (%s, %s, %s, 'indexed', %s)
            ON CONFLICT (source_file) WHERE source_file IS NOT NULL DO NOTHING
            """,
            rows,
        )
        conn.commit()


def create_document(name: str, type_: str, status: str) -> Document:
    """Tạo tài liệu THỦ CÔNG — luôn không gắn nguồn (draft/placeholder). Tài liệu có nguồn
    do `sync_kb_documents` tự tạo từ kho, không qua đây."""
    doc_id = str(uuid.uuid4())
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO documents (id, name, type, status, source_file) "
            f"VALUES (%s, %s, %s, %s, NULL) RETURNING {_COLS}",
            (doc_id, name, type_, status),
        )
        row = cur.fetchone()
        conn.commit()
    assert row is not None
    return _to_document(row, {})


def list_documents() -> list[Document]:
    """Danh mục = tài liệu đã lưu + nguồn trong kho (tự đồng bộ vào trước khi đọc)."""
    counts = kb_counts()
    sync_kb_documents(list(counts))
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {_COLS} FROM documents ORDER BY created_at DESC")
        rows = cur.fetchall()
    return [_to_document(r, counts) for r in rows]


def get_document(document_id: str) -> Document | None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {_COLS} FROM documents WHERE id = %s", (document_id,))
        row = cur.fetchone()
    return _to_document(row, kb_counts()) if row else None


def update_document(document_id: str, fields: dict[str, Any]) -> Document | None:
    """Cập nhật một phần (PATCH). `fields` chỉ chứa cột trong `UPDATABLE_COLS`."""
    fields = {k: v for k, v in fields.items() if k in UPDATABLE_COLS}
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
    return _to_document(row, kb_counts()) if row else None


def delete_document(document_id: str) -> bool:
    """Xoá khỏi danh mục. CHỈ dùng cho tài liệu KHÔNG gắn nguồn (API chặn phần còn lại):
    tài liệu có nguồn mà xoá thì lần list sau `sync_kb_documents` lại dựng lên — xoá thật
    phải xoá cả chunk khỏi kho, việc đó thuộc Bước 1 (xem CLAUDE.md)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM documents WHERE id = %s", (document_id,))
        deleted = cur.rowcount > 0
        conn.commit()
    return deleted
