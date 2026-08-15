"""Data access cho activity_log — ghi (middleware) + đọc (admin feed).

Bảng `activity_log` do BACKEND sở hữu (DDL trong core/db.py, tạo bởi init_db.py) nên luôn
tồn tại — KHÔNG cần bắt `UndefinedTable` như models/cost.py (bảng đó do agent-service tạo
lazy). Mọi hàm SYNC; API/middleware gọi qua anyio.to_thread. Xem activity-log-plan.md §4.2.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.core.db import connection

logger = logging.getLogger("backend.activity")

_INSERT_SQL = """
INSERT INTO activity_log (
    id, request_id, user_id, method, path, status_code, severity, latency_ms, error
)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
"""

# Cột trả cho tầng đọc (created_at cast text để Pydantic parse datetime ổn định).
_SELECT_COLS = (
    "id, created_at, request_id, user_id, method, path, status_code, severity, "
    "latency_ms, error"
)

def record_activity(
    *,
    request_id: str | None,
    user_id: str | None,
    method: str,
    path: str,
    status_code: int,
    severity: str,
    latency_ms: int | None,
    error: str | None,
) -> None:
    """INSERT 1 dòng activity. NUỐT mọi exception — ghi log KHÔNG được làm fail request thật
    (cùng triết lý agent-service record_usage)."""
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                _INSERT_SQL,
                (
                    str(uuid.uuid4()),
                    request_id,
                    user_id,
                    method,
                    path,
                    status_code,
                    severity,
                    latency_ms,
                    error,
                ),
            )
    except Exception as exc:  # noqa: BLE001 — log lỗi không được làm fail request
        logger.warning("record_activity bỏ qua (path=%s): %s", path, type(exc).__name__)

def list_activity(
    *,
    severity: str | None = None,
    path: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Dòng activity mới nhất trước, kèm `total` khớp filter (cho phân trang). Lọc tùy chọn
    theo severity (khớp đúng), path (ILIKE substring), khoảng ngày trên created_at."""
    where: list[str] = []
    params: list[Any] = []
    if severity:
        where.append("severity = %s")
        params.append(severity)
    if path:
        where.append("path ILIKE %s")
        params.append(f"%{path}%")
    if from_date:
        where.append("created_at::date >= %s")
        params.append(from_date)
    if to_date:
        where.append("created_at::date <= %s")
        params.append(to_date)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT count(*) AS n FROM activity_log {where_sql}", params)
        count_row = cur.fetchone()
        total = int(count_row["n"]) if count_row else 0
        cur.execute(
            f"SELECT {_SELECT_COLS} FROM activity_log {where_sql} "
            f"ORDER BY created_at DESC LIMIT %s OFFSET %s",
            [*params, limit, offset],
        )
        rows = cur.fetchall()
    for r in rows:
        r["id"] = str(r["id"])
    return rows, total
