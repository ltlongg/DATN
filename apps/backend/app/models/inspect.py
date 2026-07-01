"""Data access read-only cho KB Inspector: `rag_chunks` + `timeline_events`.

Hai bảng này do agent-service sở hữu DDL nhưng nằm CÙNG Postgres, nên backend query
thẳng qua `connection()` (không cần HTTP proxy — chỉ graph ở Neo4j mới phải proxy). Mọi
hàm SYNC; API layer gọi qua anyio.to_thread. KHÔNG có hàm ghi (read-only tuyệt đối).

Xem backend-additions-plan.md §2.1.
"""

from __future__ import annotations

from typing import Any

from app.core.db import connection

# Số ký tự preview text cắt cho danh sách chunk (đủ để nhận ra nội dung, không kéo cả chunk).
_PREVIEW_CHARS = 200


# --- chunks (rag_chunks) ---


def list_chunks(
    q: str | None, heading: str | None, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    """List chunk (preview) + tổng count. Search text ILIKE %q%; lọc heading_path chứa
    `heading`. Sort theo chunk_index (thứ tự đọc), fallback chunk_id."""
    where: list[str] = []
    params: list[Any] = []
    if q:
        where.append("text ILIKE %s")
        params.append(f"%{q}%")
    if heading:
        where.append("heading_path @> ARRAY[%s]::text[]")
        params.append(heading)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) AS n FROM rag_chunks {where_sql}", params)
        count_row = cur.fetchone()
        total = int(count_row["n"]) if count_row else 0
        cur.execute(
            f"SELECT chunk_id, heading_path, "
            f"metadata->>'source_file' AS source_file, "
            f"(metadata->>'start_line')::int AS start_line, "
            f"(metadata->>'end_line')::int AS end_line, "
            f"left(text, {_PREVIEW_CHARS}) AS preview "
            f"FROM rag_chunks {where_sql} "
            f"ORDER BY (metadata->>'chunk_index')::int ASC NULLS LAST, chunk_id ASC "
            f"LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        rows = cur.fetchall()
    return rows, total


def get_chunk(chunk_id: str) -> dict[str, Any] | None:
    """Full text + metadata JSONB + heading_path của một chunk."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT chunk_id, text, metadata, heading_path FROM rag_chunks "
            "WHERE chunk_id = %s",
            (chunk_id,),
        )
        return cur.fetchone()


def list_events_for_chunk(chunk_id: str) -> list[dict[str, Any]]:
    """Event tham chiếu chunk (`source_chunk_ids @> [chunk_id]`) — panel 'được tham chiếu
    bởi' phía event. Entity dùng cơ chế khác (proxy agent-service /kb/entities?chunk_id)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT event_id, label, time_start, time_end, confidence "
            "FROM timeline_events WHERE source_chunk_ids @> ARRAY[%s]::text[] "
            "ORDER BY time_start ASC NULLS LAST, label ASC",
            (chunk_id,),
        )
        return cur.fetchall()


# --- events (timeline_events) ---


def list_events(
    q: str | None, confidence: str | None, limit: int, offset: int
) -> tuple[list[dict[str, Any]], int]:
    """List event + tổng count. Search label/summary; lọc confidence; sort time_start."""
    where: list[str] = []
    params: list[Any] = []
    if q:
        where.append("(label ILIKE %s OR summary ILIKE %s)")
        params.extend([f"%{q}%", f"%{q}%"])
    if confidence:
        where.append("confidence = %s")
        params.append(confidence)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) AS n FROM timeline_events {where_sql}", params)
        count_row = cur.fetchone()
        total = int(count_row["n"]) if count_row else 0
        cur.execute(
            f"SELECT event_id, label, time_start, time_end, locations, confidence "
            f"FROM timeline_events {where_sql} "
            f"ORDER BY time_start ASC NULLS LAST, label ASC "
            f"LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        rows = cur.fetchall()
    return rows, total


def get_event(event_id: str) -> dict[str, Any] | None:
    """Chi tiết event đầy đủ (kèm summary, parent_event_norm, source_chunk_ids)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT event_id, label, summary, time_start, time_end, locations, "
            "confidence, parent_event_norm, source_chunk_ids "
            "FROM timeline_events WHERE event_id = %s",
            (event_id,),
        )
        return cur.fetchone()
