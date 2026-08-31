"""Postgres source of truth cho kho atomic event (lớp timeline + map).

Mirror pattern `chunk_store.py`: `CREATE TABLE IF NOT EXISTS`, `_database_url()`
strip `+psycopg`, GIN index cho mảng. Khác một điểm có chủ ý: nạp dữ liệu bằng
`replace_timeline_events()` = **TRUNCATE rồi insert trọn bộ** (không upsert lẻ).
Lý do: reconcile chạy lại có thể đổi `event_id` (đổi prompt/đổi gom nhóm) -> upsert
sẽ để lại dòng rác mang id cũ. Phần đắt (LLM extract) đã được cache, nên nạp lại
toàn bảng rất rẻ.

Khoá join online: `source_chunk_ids && retrieved_chunk_ids` (toán tử mảng giao `&&`
chạy trên GIN index).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import psycopg

from app.core.config import get_settings
from app.core.postgres import connection

CREATE_TIMELINE_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS timeline_events (
    event_id TEXT PRIMARY KEY,
    label TEXT NOT NULL,
    summary TEXT NOT NULL,
    time_start TEXT,
    time_end TEXT,
    locations TEXT[] NOT NULL DEFAULT '{}',
    confidence TEXT NOT NULL,
    parent_event_norm TEXT,
    source_chunk_ids TEXT[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

CREATE_INDEX_SQLS = [
    # Query online chính: lọc event theo chunk đã retrieve (mảng giao nhau).
    "CREATE INDEX IF NOT EXISTS timeline_events_chunks_gin "
    "ON timeline_events USING GIN (source_chunk_ids);",
    "CREATE INDEX IF NOT EXISTS timeline_events_locations_gin "
    "ON timeline_events USING GIN (locations);",
    "CREATE INDEX IF NOT EXISTS timeline_events_time_idx "
    "ON timeline_events (time_start);",
    "CREATE INDEX IF NOT EXISTS timeline_events_parent_idx "
    "ON timeline_events (parent_event_norm);",
]

INSERT_TIMELINE_EVENT_SQL = """
INSERT INTO timeline_events (
    event_id,
    label,
    summary,
    time_start,
    time_end,
    locations,
    confidence,
    parent_event_norm,
    source_chunk_ids
) VALUES (
    %s, %s, %s, %s, %s, %s::text[], %s, %s, %s::text[]
)
ON CONFLICT (event_id) DO UPDATE SET
    label = EXCLUDED.label,
    summary = EXCLUDED.summary,
    time_start = EXCLUDED.time_start,
    time_end = EXCLUDED.time_end,
    locations = EXCLUDED.locations,
    confidence = EXCLUDED.confidence,
    parent_event_norm = EXCLUDED.parent_event_norm,
    source_chunk_ids = EXCLUDED.source_chunk_ids,
    updated_at = now();
"""


def _database_url(database_url: str | None = None) -> str:
    url = database_url or get_settings().database_url
    if not url:
        raise RuntimeError("Thiếu DATABASE_URL trong .env để ghi timeline_events.")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def _empty_to_none(value: Any) -> Any:
    """Chuỗi rỗng -> NULL (schema strict dùng '' cho 'không có')."""
    if isinstance(value, str) and not value.strip():
        return None
    return value


def _record_params(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["event_id"],
        record["label"],
        record["summary"],
        _empty_to_none(record.get("time_start")),
        _empty_to_none(record.get("time_end")),
        record.get("locations") or [],
        record["confidence"],
        _empty_to_none(record.get("parent_event_norm")),
        record.get("source_chunk_ids") or [],
    )


def ensure_timeline_table(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(CREATE_TIMELINE_EVENTS_SQL)
        for sql in CREATE_INDEX_SQLS:
            cur.execute(sql)


def replace_timeline_events(
    records: Iterable[dict[str, Any]], database_url: str | None = None
) -> int:
    """Nạp TRỌN BỘ kho event: tạo bảng (nếu cần) -> TRUNCATE -> insert tất cả.

    Atomic trong một transaction: lỗi giữa chừng -> rollback, bảng cũ còn nguyên.
    Trả số dòng đã nạp.
    """
    rows = list(records)

    with psycopg.connect(_database_url(database_url)) as conn:
        ensure_timeline_table(conn)
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE timeline_events;")
            if rows:
                cur.executemany(
                    INSERT_TIMELINE_EVENT_SQL, [_record_params(r) for r in rows]
                )
        conn.commit()
    return len(rows)


def select_events_by_chunks(
    chunk_ids: list[str], database_url: str | None = None
) -> list[dict[str, Any]]:
    """Lấy event có `source_chunk_ids` giao với `chunk_ids` (khoá join online).

    Sắp theo thời gian (NULL cuối) để timeline dựng sẵn thứ tự.
    """
    if not chunk_ids:
        return []

    with connection(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM timeline_events
                WHERE source_chunk_ids && %s::text[]
                ORDER BY time_start ASC NULLS LAST, label ASC
                """,
                (chunk_ids,),
            )
            return list(cur.fetchall())


def select_location_counts(database_url: str | None = None) -> dict[str, int]:
    """Đếm số event tham chiếu mỗi địa danh (surface form) trong `timeline_events`.

    Nguồn để build gazetteer: chỉ gom các địa danh THỰC SỰ xuất hiện trong event
    (đúng thứ marker cần). Trả {surface_form: số_event}.
    """
    with psycopg.connect(_database_url(database_url)) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT location, count(*) AS n
                FROM (SELECT unnest(locations) AS location FROM timeline_events) t
                GROUP BY location
                """
            )
            return {row[0]: int(row[1]) for row in cur.fetchall()}
