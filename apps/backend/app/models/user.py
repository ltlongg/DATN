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
    is_active: bool = True
    question_quota: int | None = None  # None = không giới hạn
    created_at: datetime


def _row_to_user(row: dict[str, Any]) -> User:
    return User(
        id=str(row["id"]),
        email=row["email"],
        name=row["name"],
        role=row["role"],
        password_hash=row["password_hash"],
        is_active=row["is_active"],
        question_quota=row["question_quota"],
        created_at=row["created_at"],
    )


_SELECT = (
    "SELECT id, email, name, role, password_hash, is_active, question_quota, created_at "
    "FROM users"
)


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


_RETURNING = "id, email, name, role, password_hash, is_active, question_quota, created_at"


def create_user(email: str, name: str, role: Role, password_hash: str) -> User:
    user_id = str(uuid.uuid4())
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO users (id, email, name, role, password_hash) "
            f"VALUES (%s, %s, %s, %s, %s) RETURNING {_RETURNING}",
            (user_id, email, name, role, password_hash),
        )
        row = cur.fetchone()
        conn.commit()
    assert row is not None  # RETURNING luôn có 1 dòng sau INSERT thành công
    return _row_to_user(row)


def list_users() -> list[User]:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"{_SELECT} ORDER BY created_at ASC")
        rows = cur.fetchall()
    return [_row_to_user(r) for r in rows]


def update_user(user_id: str, fields: dict[str, Any]) -> User | None:
    """PATCH một phần (role/is_active/question_quota). `fields` đã lọc cột hợp lệ ở API."""
    if not fields:
        return get_user_by_id(user_id)
    set_clause = ", ".join(f"{col} = %s" for col in fields)
    params = [*fields.values(), user_id]
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE users SET {set_clause} WHERE id = %s RETURNING {_RETURNING}",
            params,
        )
        row = cur.fetchone()
        conn.commit()
    return _row_to_user(row) if row else None
