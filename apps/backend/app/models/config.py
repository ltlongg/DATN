"""Data access cho bảng `system_config` — psycopg trực tiếp, không ORM.

Backend SỞ HỮU bảng này (DDL ở core/db.py, singleton id=1 seed sẵn khi init_schema). Khác
các store index-time (rag_chunks/timeline_events), agent-service KHÔNG query bảng này trực
tiếp — nó đọc qua endpoint nội bộ GET /internal/config của backend (xem system-config-plan.md
§Storage roles). Hàm SYNC; API layer gọi qua anyio.to_thread.
"""

from __future__ import annotations

from typing import Any

import psycopg

from app.core.db import connection
from app.core.errors import AppError
from app.schemas.config import SystemConfigResponse

# Thứ tự cột khớp SystemConfigResponse; dùng cho cả SELECT lẫn RETURNING.
_COLUMNS = (
    "rag_top_k",
    "graph_top_k",
    "hybrid_candidate_k",
    "hybrid_rrf_k",
    "rerank_top_k",
    "bm25_top_k",
    "graph_max_seed_entities",
    "graph_max_chunks_per_seed",
    "graph_hub_source_count_threshold",
    "graph_max_context_items",
    "graph_max_path_hops",
    "graph_path_hit_weight",
    "updated_at",
)
_SELECT_LIST = ", ".join(_COLUMNS)

def get_config() -> SystemConfigResponse:
    """Đọc dòng singleton (id=1). Row luôn tồn tại vì init_schema INSERT sẵn."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT {_SELECT_LIST} FROM system_config WHERE id = 1")
        row = cur.fetchone()
    if row is None:
        raise AppError(
            500, "internal_error", "system_config chưa được khởi tạo (chạy init_db)."
        )
    return SystemConfigResponse(**row)

def update_config(fields: dict[str, Any]) -> SystemConfigResponse:
    """PATCH một phần (fields đã lọc exclude_unset ở API). Cập nhật updated_at; trả dòng mới.

    DB CHECK (range + rerank_top_k <= hybrid_candidate_k) là lưới an toàn cuối cho PATCH lẻ mà
    schema không kiểm hết được -> map CheckViolation về 422 thay vì 500 thô.
    """
    if not fields:
        return get_config()
    set_clause = ", ".join(f"{col} = %s" for col in fields)
    params = [*fields.values()]
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                f"UPDATE system_config SET {set_clause}, updated_at = now() "
                f"WHERE id = 1 RETURNING {_SELECT_LIST}",
                params,
            )
            row = cur.fetchone()
            conn.commit()
    except psycopg.errors.CheckViolation as exc:
        raise AppError(
            422, "validation_error", "Giá trị cấu hình vi phạm ràng buộc hợp lệ."
        ) from exc
    if row is None:
        # Row id=1 luôn được init_schema INSERT sẵn; nếu bị xoá -> báo rõ như get_config
        # (KHÔNG assert: assert bị strip khi chạy python -O -> AssertionError khó hiểu).
        raise AppError(
            500, "internal_error", "system_config chưa được khởi tạo (chạy init_db)."
        )
    return SystemConfigResponse(**row)
