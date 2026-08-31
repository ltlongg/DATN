"""Postgres bảng `gazetteer`: toạ độ do người dùng tự tra và điền tay.

Mirror pattern `chunk_store.py`. Khác `timeline_events`: gazetteer dùng UPSERT lẻ
(`ON CONFLICT DO UPDATE`) vì khoá `location_norm` ổn định (không đổi khi re-run),
build dần qua nhiều đợt điền tay mà không cần nạp lại cả bảng.

Khoá `location_norm = normalize_name(location)` để join với từng phần tử trong
`timeline_events.locations` (builder online chuẩn hoá trước khi tra).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import psycopg

from app.core.config import get_settings
from app.core.postgres import connection

CREATE_GAZETTEER_SQL = """
CREATE TABLE IF NOT EXISTS gazetteer (
    location_norm TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    lat DOUBLE PRECISION,
    lon DOUBLE PRECISION,
    note TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

# Bảng cũ sinh từ thời geocode tự động còn `confidence`/`status`; dọn khi mở kết nối
# để không phải migrate tay trên môi trường đã chạy pipeline cũ.
MIGRATE_GAZETTEER_SQLS = [
    "ALTER TABLE gazetteer ADD COLUMN IF NOT EXISTS note TEXT NOT NULL DEFAULT '';",
    "ALTER TABLE gazetteer DROP COLUMN IF EXISTS confidence;",
    "ALTER TABLE gazetteer DROP COLUMN IF EXISTS status;",
]

UPSERT_GAZETTEER_SQL = """
INSERT INTO gazetteer (
    location_norm,
    display_name,
    lat,
    lon,
    note
) VALUES (
    %s, %s, %s, %s, %s
)
ON CONFLICT (location_norm) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    lat = EXCLUDED.lat,
    lon = EXCLUDED.lon,
    note = EXCLUDED.note,
    updated_at = now();
"""

def _database_url(database_url: str | None = None) -> str:
    url = database_url or get_settings().database_url
    if not url:
        raise RuntimeError("Thiếu DATABASE_URL trong .env để ghi gazetteer.")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)

def _record_params(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["location_norm"],
        record["display_name"],
        record.get("lat"),
        record.get("lon"),
        record.get("note") or "",
    )

def ensure_gazetteer_table(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(CREATE_GAZETTEER_SQL)
        for sql in MIGRATE_GAZETTEER_SQLS:
            cur.execute(sql)

def upsert_gazetteer(
    records: Iterable[dict[str, Any]], database_url: str | None = None
) -> int:
    """Tạo bảng nếu cần và upsert địa danh. Trả số dòng đã ghi."""
    rows = list(records)
    if not rows:
        return 0

    with psycopg.connect(_database_url(database_url)) as conn:
        ensure_gazetteer_table(conn)
        with conn.cursor() as cur:
            cur.executemany(UPSERT_GAZETTEER_SQL, [_record_params(r) for r in rows])
        conn.commit()
    return len(rows)

def lookup_coords(
    location_norms: list[str], database_url: str | None = None
) -> dict[str, dict[str, Any]]:
    """Tra toạ độ cho danh sách `location_norm`. Trả dict {location_norm: row}.

    Địa danh chưa được tra toạ độ (lat/lon NULL) -> không xuất hiện trong dict, builder
    coi như không có toạ độ -> chỉ lên timeline, không marker.

    Bảng CHƯA TỒN TẠI (`build_gazetteer.py --sync-db` chưa chạy lần nào) -> coi như
    chưa có địa danh nào. Không để lỗi này giết cả `build_visualization`: timeline vốn
    độc lập với toạ độ, mất nó là mất trắng phần trực quan hoá dù dữ liệu thời gian vẫn
    đủ.
    """
    if not location_norms:
        return {}

    try:
        with connection(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT * FROM gazetteer
                    WHERE location_norm = ANY(%s::text[])
                      AND lat IS NOT NULL
                      AND lon IS NOT NULL
                    """,
                    (location_norms,),
                )
                return {row["location_norm"]: row for row in cur.fetchall()}
    except (psycopg.errors.UndefinedTable, psycopg.errors.UndefinedColumn):
        return {}
