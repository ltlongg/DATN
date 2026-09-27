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
    "retrieval_mode, confidence, warnings, steps, ttft_ms, created_at"
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

# Chủ hội thoại, kèm mã ẩn danh `user-xxxxxxxx` = md5(secret || user id). Có secret nên admin
# không tự tính lại từ user id được (không đối chiếu ngược ra người thật); cùng user luôn ra
# cùng mã nên vẫn gom được hội thoại theo người. Tham số duy nhất: secret.
_OWNERS_CTE = (
    "WITH owners AS (SELECT id, email, name, share_conversations, "
    "'user-' || left(md5(%s || id::text), 8) AS anon_id FROM users) "
)

def list_conversations_admin(
    secret: str,
    user_anon_id: str | None,
    flagged_only: bool,
    from_date: str | None,
    to_date: str | None,
    limit: int,
    offset: int,
) -> tuple[list[dict[str, Any]], int]:
    """List conversation (mọi user) + chủ sở hữu + số message/số tin bị gắn cờ; lọc theo mã
    ẩn danh / chỉ hội thoại có tin bị gắn cờ / khoảng ngày. Trả cột THÔ (cả email/tên/title)
    — API quyết định cái gì được lộ."""
    where, params = _date_filters(from_date, to_date, "c.updated_at")
    if user_anon_id:
        where.append("o.anon_id = %s")
        params.append(user_anon_id)
    if flagged_only:
        where.append(
            "EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id AND m.flagged)"
        )
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    from_sql = f"FROM conversations c JOIN owners o ON o.id = c.user_id {where_sql} "

    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"{_OWNERS_CTE}SELECT count(*) AS n {from_sql}", [secret, *params])
        count_row = cur.fetchone()
        total = int(count_row["n"]) if count_row else 0
        cur.execute(
            f"{_OWNERS_CTE}SELECT c.id, c.title, c.created_at, c.updated_at, "
            f"o.email AS user_email, o.name AS user_name, o.anon_id AS user_anon_id, "
            f"o.share_conversations AS shared, "
            f"(SELECT count(*) FROM messages m WHERE m.conversation_id = c.id) "
            f"AS message_count, "
            f"(SELECT count(*) FROM messages m WHERE m.conversation_id = c.id AND m.flagged) "
            f"AS flagged_count "
            f"{from_sql}"
            f"ORDER BY c.updated_at DESC LIMIT %s OFFSET %s",
            [secret, *params, limit, offset],
        )
        rows = cur.fetchall()
    for r in rows:
        r["id"] = str(r["id"])
    return rows, total

def get_conversation_detail_admin(secret: str, conversation_id: str) -> dict[str, Any] | None:
    """Conversation + owner + TẤT CẢ message (thô, kèm cờ vi phạm). None nếu không tồn tại."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"{_OWNERS_CTE}SELECT c.id, c.title, c.created_at, c.updated_at, "
            f"o.email AS user_email, o.name AS user_name, o.anon_id AS user_anon_id, "
            f"o.share_conversations AS shared "
            f"FROM conversations c JOIN owners o ON o.id = c.user_id WHERE c.id = %s",
            (secret, conversation_id),
        )
        conv = cur.fetchone()
        if conv is None:
            return None
        cur.execute(
            f"SELECT {_MSG_COLS}, flagged, flag_categories FROM messages "
            f"WHERE conversation_id = %s ORDER BY created_at ASC, id ASC",
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
