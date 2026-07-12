"""Data access read-only cho Module 4 — Hội thoại & chất lượng (admin).

Không đụng `models/conversation.py` (dùng cho user thường). Ở đây JOIN `users` để lấy
chủ sở hữu và trả cột thô cho tầng service tính chất lượng. Mọi hàm SYNC; API gọi qua
anyio.to_thread. Xem backend-additions-plan.md §3.1.
"""

from __future__ import annotations

from typing import Any

import psycopg

from app.core.db import connection

# Cột thô của message (không tính chất lượng ở SQL — để service thuần xử lý).
_MSG_COLS = (
    "id, role, content, clarification_needed, citations, visualization, "
    "retrieval_mode, confidence, warnings, ttft_ms, created_at"
)


def _date_filters(
    from_date: str | None, to_date: str | None, column: str
) -> tuple[list[str], list[Any]]:
    """Điều kiện lọc theo khoảng ngày trên `column` (so sánh phần ::date)."""
    where: list[str] = []
    params: list[Any] = []
    if from_date:
        where.append(f"{column}::date >= %s")
        params.append(from_date)
    if to_date:
        where.append(f"{column}::date <= %s")
        params.append(to_date)
    return where, params


def list_conversations_admin(
    user_email: str | None,
    from_date: str | None,
    to_date: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """List conversation (mọi user) + chủ sở hữu + số message; lọc email/khoảng ngày."""
    where, params = _date_filters(from_date, to_date, "c.updated_at")
    if user_email:
        where.append("u.email = %s")
        params.append(user_email)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT count(*) AS n FROM conversations c JOIN users u ON u.id = c.user_id "
            f"{where_sql}",
            params,
        )
        count_row = cur.fetchone()
        total = int(count_row["n"]) if count_row else 0
        cur.execute(
            f"SELECT c.id, c.title, c.created_at, c.updated_at, "
            f"u.email AS user_email, u.name AS user_name, "
            f"(SELECT count(*) FROM messages m WHERE m.conversation_id = c.id) "
            f"AS message_count "
            f"FROM conversations c JOIN users u ON u.id = c.user_id "
            f"{where_sql} "
            f"ORDER BY c.updated_at DESC LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        rows = cur.fetchall()
    for r in rows:
        r["id"] = str(r["id"])
    return rows, total


def get_conversation_detail_admin(conversation_id: str) -> dict[str, Any] | None:
    """Conversation + owner + TẤT CẢ message (thô). None nếu không tồn tại."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT c.id, c.title, c.created_at, c.updated_at, "
            "u.email AS user_email, u.name AS user_name "
            "FROM conversations c JOIN users u ON u.id = c.user_id WHERE c.id = %s",
            (conversation_id,),
        )
        conv = cur.fetchone()
        if conv is None:
            return None
        cur.execute(
            f"SELECT {_MSG_COLS} FROM messages WHERE conversation_id = %s "
            f"ORDER BY created_at ASC, id ASC",
            (conversation_id,),
        )
        messages = cur.fetchall()
    conv["id"] = str(conv["id"])
    for m in messages:
        m["id"] = str(m["id"])
    conv["messages"] = messages
    return conv


def list_quality_rows(
    from_date: str | None = None, to_date: str | None = None
) -> list[dict[str, Any]]:
    """Cột thô của assistant message trong khoảng thời gian (không tính toán ở SQL)."""
    where, params = _date_filters(from_date, to_date, "created_at")
    where.append("role = 'assistant'")
    where_sql = "WHERE " + " AND ".join(where)
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"SELECT confidence, citations, clarification_needed, warnings, "
            f"retrieval_mode, ttft_ms, created_at FROM messages {where_sql}",
            params,
        )
        return cur.fetchall()


# --- Token usage (đọc thẳng llm_usage; agent-service sở hữu DDL, tạo lazy) -----------------
# Cả 2 hàm bắt UndefinedTable -> [] (y hệt models/cost.py): admin có thể mở tab Hội thoại
# TRƯỚC câu hỏi đầu tiên (llm_usage chưa tồn tại) mà không 500.


def list_attributed_usage_rows(
    from_date: str | None = None, to_date: str | None = None
) -> list[dict[str, Any]]:
    """Usage rows CÓ conversation_id (bỏ row cũ NULL — không backfill) trong khoảng ngày.
    Nguồn cho card tổng + cột token theo hội thoại. Bảng chưa tồn tại -> []."""
    where, params = _date_filters(from_date, to_date, "created_at")
    where.append("conversation_id IS NOT NULL")
    where_sql = "WHERE " + " AND ".join(where)
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT conversation_id, prompt_tokens, completion_tokens, total_tokens "
                f"FROM llm_usage {where_sql}",
                params,
            )
            return cur.fetchall()
    except psycopg.errors.UndefinedTable:
        return []


def get_message_token_rows(conversation_id: str) -> list[dict[str, Any]]:
    """Usage của 1 hội thoại, gộp theo (message_id, task, model) cho breakdown chi tiết.
    Đọc thẳng llm_usage theo conversation_id (không JOIN messages) nên orphan usage vẫn ra —
    FE map theo message_id, dòng nào không khớp message hiển thị vẫn gom được. Bảng chưa tồn
    tại -> []."""
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT message_id, task, model, "
                "sum(prompt_tokens) AS prompt_tokens, "
                "sum(completion_tokens) AS completion_tokens, "
                "sum(total_tokens) AS total_tokens "
                "FROM llm_usage WHERE conversation_id = %s AND message_id IS NOT NULL "
                "GROUP BY message_id, task, model "
                "ORDER BY message_id, task",
                (conversation_id,),
            )
            return cur.fetchall()
    except psycopg.errors.UndefinedTable:
        return []
