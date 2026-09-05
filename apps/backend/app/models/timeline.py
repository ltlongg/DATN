"""Data access read-only cho trang "Dòng lịch sử" (user) — feed biên niên toàn kho.

Khác `models/inspect.py` (KB Inspector, admin, tra cứu từng dòng): ở đây là MỘT feed
cuộn liên tục theo thứ tự thời gian. `timeline_events` do agent-service sở hữu DDL
nhưng cùng Postgres nên query thẳng. Mọi hàm SYNC; API layer gọi qua anyio.to_thread.

Xem docs/plan/timeline-explorer-plan.md §3.2.
"""

from __future__ import annotations

from typing import Any

import psycopg

from app.core.db import connection

# `time_sort IS NOT NULL` gộp cả hai điều kiện: event không có mốc (time_start NULL) và
# mốc không parse được (vd "9 tháng" — LLM lấy độ dài làm mốc) đều có khoá NULL. Cùng
# một điều kiện cho count và cho rows -> `total` khớp đúng số item cuộn được.
_WHERE = "WHERE e.time_sort IS NOT NULL"

# Cùng một mốc thì giữ nguyên MẠCH KỂ của sách, theo hai bậc: `source_chunk_ids[1]` (vd
# 'tap2_clean-000358') cho thứ tự GIỮA các chunk, rồi `seq` cho thứ tự TRONG một chunk.
# Thiếu `seq` thì nhiều event cùng chunk hoà nhau và rơi xuống xếp theo `label`, tức
# alphabet — mà alphabet ở collation en_US còn đặt 'đ' sau cả 'z', nên mạch kể loạn hẳn.
# Ba khoá này đã đủ TẤT ĐỊNH (điều kiện bắt buộc: LIMIT/OFFSET trên thứ tự đổi giữa hai
# lần query sẽ lặp dòng trang này, nuốt dòng trang kia). Cặp (chunk, seq) là toạ độ nơi
# record ra đời trong cache, mà `enumerate` không phát lại chỉ số trong cùng một chunk ->
# không hoà được. Đã đo trên dữ liệu thật: 0 bộ ba trùng / 3785 dòng.
_ORDER = "ORDER BY e.time_sort ASC, e.source_chunk_ids[1] ASC, e.seq ASC NULLS LAST"


def list_timeline_cards(limit: int, offset: int) -> tuple[list[dict[str, Any]], int]:
    """Một trang thẻ sự kiện (đã sắp theo thời gian) + tổng số thẻ cuộn được.

    Bảng chưa tồn tại (DB trống, chưa chạy indexing) -> ([], 0) theo pattern
    `models/cost.py`, tránh 500 thô.
    """
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(f"SELECT count(*) AS n FROM timeline_events e {_WHERE}")
            count_row = cur.fetchone()
            total = int(count_row["n"]) if count_row else 0
            cur.execute(
                f"SELECT e.event_id, e.label, e.summary, e.time_start, e.time_end, "
                f"e.locations, e.confidence "
                f"FROM timeline_events e {_WHERE} {_ORDER} "
                f"LIMIT %s OFFSET %s",
                (limit, offset),
            )
            rows = cur.fetchall()
        return rows, total
    except psycopg.errors.UndefinedTable:
        return [], 0
