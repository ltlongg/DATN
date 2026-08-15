"""Data access read-only cho Module 4 — Chi phí (admin).

`llm_usage` do agent-service sở hữu DDL nhưng cùng Postgres -> backend query thẳng (giống
rag_chunks/timeline_events; chỉ Neo4j mới cần proxy). Bảng này tạo LAZY trong record_usage()
nên có thể CHƯA TỒN TẠI khi admin mở tab Chi phí trước câu hỏi đầu tiên -> bắt
`UndefinedTable` trả `[]` (coi như chưa có usage), tránh 500 thô. Xem backend-additions-plan
§4.2.
"""

from __future__ import annotations

from typing import Any

import psycopg

from app.core.db import connection

def _date_filters(
    from_date: str | None, to_date: str | None, column: str = "created_at"
) -> tuple[list[str], list[Any]]:
    """`column` qualify được (vd 'l.created_at' khi JOIN users cũng có created_at)."""
    where: list[str] = []
    params: list[Any] = []
    if from_date:
        where.append(f"{column}::date >= %s")
        params.append(from_date)
    if to_date:
        where.append(f"{column}::date <= %s")
        params.append(to_date)
    return where, params

def list_usage_rows(
    from_date: str | None = None, to_date: str | None = None
) -> list[dict[str, Any]]:
    """Cột thô của usage trong khoảng thời gian (không tính toán ở SQL). Bảng chưa tồn tại
    -> []."""
    where, params = _date_filters(from_date, to_date)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT created_at, task, prompt_tokens, completion_tokens, total_tokens "
                f"FROM llm_usage {where_sql}",
                params,
            )
            return cur.fetchall()
    except psycopg.errors.UndefinedTable:
        return []

def list_top_users(
    from_date: str | None = None, to_date: str | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    """Top user theo tổng token (JOIN users; user_id là TEXT nên cast u.id::text). Bảng chưa
    tồn tại -> []."""
    where, params = _date_filters(from_date, to_date, "l.created_at")
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT u.id::text AS user_id, u.email, u.name, "
                f"sum(l.total_tokens) AS total_tokens, count(*) AS call_count "
                f"FROM llm_usage l JOIN users u ON u.id::text = l.user_id "
                f"{where_sql} "
                f"GROUP BY u.id, u.email, u.name "
                f"ORDER BY total_tokens DESC LIMIT %s",
                [*params, limit],
            )
            return cur.fetchall()
    except psycopg.errors.UndefinedTable:
        return []
