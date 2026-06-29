"""Tạo 4 bảng backend (users/conversations/messages/documents) — chạy 1 lần.

CREATE TABLE IF NOT EXISTS nên idempotent: chạy lại không phá dữ liệu. KHÔNG dùng
Alembic (xem backend-plan.md). Đổi schema về sau -> ALTER TABLE tay.

    python scripts/init_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Cho phép `python scripts/init_db.py` từ apps/backend mà vẫn import được package `app`.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.db import SCHEMA_STATEMENTS, connection, init_schema  # noqa: E402


def main() -> None:
    with connection() as conn:
        init_schema(conn)
    print(f"Đã tạo/kiểm tra {len(SCHEMA_STATEMENTS)} câu DDL cho 4 bảng backend.")


if __name__ == "__main__":
    main()
