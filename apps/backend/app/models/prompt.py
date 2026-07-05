"""Data access cho quản lý Prompt (Item 2 — admin CRUD). Đọc/ghi cùng bảng managed_prompts /
prompt_versions mà agent-service sở hữu DDL (bootstrap bằng scripts/seed_prompts.py).

Reads bắt `UndefinedTable` -> rỗng (giống models/cost.py): mở UI Prompt trước khi seed không
500. Writes chỉ chạy trên key ĐÃ seed (FK) nên giả định bảng tồn tại. Mọi hàm SYNC; API gọi
qua anyio.to_thread. `promote` chạy trong 1 connection() -> 1 transaction (commit khi thoát
sạch)."""

from __future__ import annotations

import uuid
from typing import Any

import psycopg

from app.core.db import connection

# Metadata version (KHÔNG kèm content — content có thể lớn × nhiều version; lấy riêng qua
# get_version khi cần So sánh/nạp editor).
_VERSION_META_COLS = (
    "version_no, note, status, created_by, created_at, promoted_by, promoted_at"
)


def list_prompts() -> list[dict[str, Any]]:
    """Mỗi prompt: meta + version_no production hiện hành + số version. Bảng chưa seed -> []."""
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT m.key, m.grp, m.title, m.description, m.updated_at, "
                "(SELECT v.version_no FROM prompt_versions v "
                " WHERE v.prompt_key = m.key AND v.status = 'production' "
                " ORDER BY v.version_no DESC LIMIT 1) AS active_version_no, "
                "(SELECT count(*) FROM prompt_versions v WHERE v.prompt_key = m.key) "
                "AS version_count "
                "FROM managed_prompts m ORDER BY m.grp, m.key"
            )
            rows = cur.fetchall()
    except psycopg.errors.UndefinedTable:
        return []
    for r in rows:
        r["version_count"] = int(r["version_count"])
    return rows


def get_prompt(key: str) -> dict[str, Any] | None:
    """Meta + versions[] (không content) + content production hiện hành. None nếu key không có
    (hoặc bảng chưa seed)."""
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT key, grp, title, description, updated_at "
                "FROM managed_prompts WHERE key = %s",
                (key,),
            )
            meta = cur.fetchone()
            if meta is None:
                return None
            cur.execute(
                f"SELECT {_VERSION_META_COLS} FROM prompt_versions "
                f"WHERE prompt_key = %s ORDER BY version_no DESC",
                (key,),
            )
            versions = cur.fetchall()
            cur.execute(
                "SELECT content FROM prompt_versions "
                "WHERE prompt_key = %s AND status = 'production' "
                "ORDER BY version_no DESC LIMIT 1",
                (key,),
            )
            prod = cur.fetchone()
    except psycopg.errors.UndefinedTable:
        return None
    meta["production_content"] = prod["content"] if prod else None
    meta["versions"] = versions
    return meta


def get_version(key: str, version_no: int) -> dict[str, Any] | None:
    """Content + status của 1 version cụ thể (phục vụ So sánh / nạp editor). None nếu không có."""
    try:
        with connection() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT version_no, content, status FROM prompt_versions "
                "WHERE prompt_key = %s AND version_no = %s",
                (key, version_no),
            )
            return cur.fetchone()
    except psycopg.errors.UndefinedTable:
        return None


def create_staging_version(
    key: str, content: str, note: str | None, by: str
) -> dict[str, Any] | None:
    """Tạo version 'staging' mới (version_no = max+1). None nếu key không tồn tại. Trả meta
    version vừa tạo."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM managed_prompts WHERE key = %s", (key,))
        if cur.fetchone() is None:
            return None
        cur.execute(
            "SELECT COALESCE(MAX(version_no), 0) + 1 AS next FROM prompt_versions "
            "WHERE prompt_key = %s",
            (key,),
        )
        next_no = int(cur.fetchone()["next"])
        cur.execute(
            f"INSERT INTO prompt_versions "
            f"(id, prompt_key, version_no, content, note, status, created_by) "
            f"VALUES (%s, %s, %s, %s, %s, 'staging', %s) "
            f"RETURNING {_VERSION_META_COLS}",
            (str(uuid.uuid4()), key, next_no, content, note, by),
        )
        created = cur.fetchone()
        cur.execute("UPDATE managed_prompts SET updated_at = now() WHERE key = %s", (key,))
    return created


def promote(key: str, version_no: int, by: str) -> bool:
    """Đẩy 1 version lên production (transaction 1 connection): production hiện tại ->
    archived; version đích -> production + ghi promoted_by/at. False nếu version không tồn tại."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM prompt_versions WHERE prompt_key = %s AND version_no = %s",
            (key, version_no),
        )
        if cur.fetchone() is None:
            return False
        cur.execute(
            "UPDATE prompt_versions SET status = 'archived' "
            "WHERE prompt_key = %s AND status = 'production'",
            (key,),
        )
        cur.execute(
            "UPDATE prompt_versions "
            "SET status = 'production', promoted_by = %s, promoted_at = now() "
            "WHERE prompt_key = %s AND version_no = %s",
            (by, key, version_no),
        )
        cur.execute("UPDATE managed_prompts SET updated_at = now() WHERE key = %s", (key,))
    return True
