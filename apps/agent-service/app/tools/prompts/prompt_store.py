"""Store cho managed prompts + versions (Item 2 — admin-restructure-plan.md).

Tách phần **system prompt tĩnh** ra Postgres để admin sửa/version/promote KHÔNG cần deploy.
Agent đọc version `production` lúc chạy; backend (service khác, cùng Postgres) đọc/ghi CRUD.

TRIẾT LÝ AN TOÀN: `get_active_prompt` LUÔN fallback về hằng trong code nếu DB chưa seed /
chưa có version production / DB lỗi -> answer flow KHÔNG bao giờ vỡ (cùng tinh thần
`record_usage` nuốt lỗi). Cache in-memory TTL ngắn để không query DB mỗi câu (đổi prompt trễ
tối đa ~TTL giây).

DDL do prompt_store SỞ HỮU (mirror chunk_store/usage_log, lazy CREATE TABLE IF NOT EXISTS).
Backend đọc/ghi cùng bảng nhưng KHÔNG tạo bảng (giống cost.py với llm_usage) — seed script
bootstrap.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import psycopg

from app.core.postgres import connection

logger = logging.getLogger("agent.prompt_store")

CREATE_MANAGED_PROMPTS_SQL = """
CREATE TABLE IF NOT EXISTS managed_prompts (
    key         TEXT PRIMARY KEY,
    grp         TEXT NOT NULL,
    title       TEXT NOT NULL,
    description TEXT,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""

CREATE_PROMPT_VERSIONS_SQL = """
CREATE TABLE IF NOT EXISTS prompt_versions (
    id           UUID PRIMARY KEY,
    prompt_key   TEXT NOT NULL REFERENCES managed_prompts(key),
    version_no   INTEGER NOT NULL,
    content      TEXT NOT NULL,
    note         TEXT,
    status       TEXT NOT NULL,
    created_by   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    promoted_by  TEXT,
    promoted_at  TIMESTAMPTZ,
    UNIQUE(prompt_key, version_no)
);
"""

CREATE_INDEX_SQLS = [
    "CREATE INDEX IF NOT EXISTS prompt_versions_key_idx ON prompt_versions (prompt_key);",
    "CREATE INDEX IF NOT EXISTS prompt_versions_status_idx ON prompt_versions (prompt_key, status);",
]


def ensure_prompt_tables(conn: psycopg.Connection[Any]) -> None:
    with conn.cursor() as cur:
        cur.execute(CREATE_MANAGED_PROMPTS_SQL)
        cur.execute(CREATE_PROMPT_VERSIONS_SQL)
        for sql in CREATE_INDEX_SQLS:
            cur.execute(sql)


# --- Runtime loader (hot path online) ---------------------------------------

_CACHE_TTL_SECONDS = 60.0
_cache: dict[str, tuple[float, str]] = {}


def clear_cache() -> None:
    """Xoá cache (test + hook bust khi promote — nếu làm sau)."""
    _cache.clear()


def _load_production_content(key: str) -> str | None:
    """Content version production mới nhất của `key`. Bảng chưa tồn tại / DB lỗi -> None
    (nuốt lỗi, để get_active_prompt fallback về hằng code)."""
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT content FROM prompt_versions "
                "WHERE prompt_key = %s AND status = 'production' "
                "ORDER BY version_no DESC LIMIT 1",
                (key,),
            )
            row = cur.fetchone()
            return row["content"] if row else None
    except Exception as exc:  # noqa: BLE001 — lỗi đọc prompt KHÔNG được làm fail answer
        logger.warning("get_active_prompt bỏ qua DB (key=%s): %s", key, type(exc).__name__)
        return None


def get_active_prompt(key: str, *, fallback: str) -> str:
    """System prompt đang hiệu lực cho `key`: version production trong DB, hoặc `fallback`
    (hằng code) nếu chưa có/lỗi. Cache kết quả ~TTL giây để không query DB mỗi câu."""
    now = time.monotonic()
    hit = _cache.get(key)
    if hit is not None and hit[0] > now:
        return hit[1]
    content = _load_production_content(key)
    resolved = content if content is not None else fallback
    _cache[key] = (now + _CACHE_TTL_SECONDS, resolved)
    return resolved


# --- Seed (idempotent) ------------------------------------------------------


def seed_prompt(key: str, grp: str, title: str, description: str, content: str) -> bool:
    """Tạo managed_prompts + version 1 (production) từ hằng code nếu key CHƯA có. Idempotent:
    key đã tồn tại -> không đụng. Trả True nếu vừa tạo mới. Dùng bởi scripts/seed_prompts.py."""
    with connection() as conn:
        ensure_prompt_tables(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM managed_prompts WHERE key = %s", (key,))
            if cur.fetchone() is not None:
                return False
            cur.execute(
                "INSERT INTO managed_prompts (key, grp, title, description) "
                "VALUES (%s, %s, %s, %s)",
                (key, grp, title, description),
            )
            cur.execute(
                "INSERT INTO prompt_versions "
                "(id, prompt_key, version_no, content, note, status, created_by) "
                "VALUES (%s, %s, 1, %s, %s, 'production', %s)",
                (str(uuid.uuid4()), key, content, "seed from code", "system"),
            )
    return True


def publish_prompt_version(key: str, content: str, *, note: str) -> int | None:
    """Đẩy hằng prompt trong CODE lên production: tạo version mới + hạ version cũ xuống archived.

    Vì sao cần: `seed_prompt` idempotent theo KEY nên sau lần seed đầu, mọi thay đổi prompt
    trong code **không bao giờ tới runtime** — `get_active_prompt` đọc bản production trong DB
    và bỏ qua hằng code (hằng chỉ còn là fallback khi DB hỏng). Không có hàm này thì sửa
    prompt xong tưởng đã chạy, thực tế agent vẫn dùng bản cũ — hỏng IM LẶNG.

    Trả `version_no` mới, hoặc None nếu content đã TRÙNG production (không đẻ version rác).
    Cùng ngữ nghĩa `promote` của backend `models/prompt.py`: một transaction, production cũ
    -> archived, ghi `promoted_by`/`promoted_at`.
    """
    with connection() as conn:
        ensure_prompt_tables(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM managed_prompts WHERE key = %s", (key,))
            if cur.fetchone() is None:
                raise ValueError(f"prompt key chưa tồn tại: {key} (chạy seed trước)")
            cur.execute(
                "SELECT content FROM prompt_versions "
                "WHERE prompt_key = %s AND status = 'production' "
                "ORDER BY version_no DESC LIMIT 1",
                (key,),
            )
            row = cur.fetchone()
            if row is not None and row["content"] == content:
                return None
            cur.execute(
                "SELECT COALESCE(MAX(version_no), 0) AS n FROM prompt_versions "
                "WHERE prompt_key = %s",
                (key,),
            )
            max_row = cur.fetchone()
            # COALESCE + không GROUP BY -> luôn đúng 1 dòng; assert để mypy khỏi đoán None.
            assert max_row is not None
            next_no = int(max_row["n"]) + 1
            cur.execute(
                "UPDATE prompt_versions SET status = 'archived' "
                "WHERE prompt_key = %s AND status = 'production'",
                (key,),
            )
            cur.execute(
                "INSERT INTO prompt_versions (id, prompt_key, version_no, content, note, "
                "status, created_by, promoted_by, promoted_at) "
                "VALUES (%s, %s, %s, %s, %s, 'production', 'system', 'system', now())",
                (str(uuid.uuid4()), key, next_no, content, note),
            )
    clear_cache()  # nếu không, agent trong tiến trình này còn đọc bản cũ tới hết TTL
    return next_no
