"""Data access cho bảng `users` — psycopg trực tiếp, không ORM.

Repo function là SYNC (mở/đóng connection riêng mỗi lần); API layer gọi qua
anyio.to_thread để không chặn event loop.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.core.db import connection
from app.schemas.common import Role


class User(BaseModel):
    id: str
    email: str
    name: str
    role: Role
    password_hash: str
    created_at: datetime


def _row_to_user(row: dict[str, Any]) -> User:
    return User(
        id=str(row["id"]),
        email=row["email"],
        name=row["name"],
        role=row["role"],
        password_hash=row["password_hash"],
        created_at=row["created_at"],
    )


_SELECT = "SELECT id, email, name, role, password_hash, created_at FROM users"


def get_user_by_email(email: str) -> User | None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"{_SELECT} WHERE email = %s", (email,))
        row = cur.fetchone()
    return _row_to_user(row) if row else None


def get_user_by_id(user_id: str) -> User | None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"{_SELECT} WHERE id = %s", (user_id,))
        row = cur.fetchone()
    return _row_to_user(row) if row else None


def create_user(email: str, name: str, role: Role, password_hash: str) -> User:
    user_id = str(uuid.uuid4())
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO users (id, email, name, role, password_hash) "
            "VALUES (%s, %s, %s, %s, %s) "
            "RETURNING id, email, name, role, password_hash, created_at",
            (user_id, email, name, role, password_hash),
        )
        row = cur.fetchone()
        conn.commit()
    assert row is not None  # RETURNING luôn có 1 dòng sau INSERT thành công
    return _row_to_user(row)
