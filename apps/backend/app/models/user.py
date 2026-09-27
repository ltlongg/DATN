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
    password_hash: str | None  # None = tài khoản Google-only, chưa đặt mật khẩu
    google_sub: str | None = None  # `sub` bất biến của Google, None = tài khoản mật khẩu
    is_active: bool = True
    question_quota: int | None = None  # None = không giới hạn
    share_conversations: bool = False  # True = cho admin đọc nội dung hội thoại
    created_at: datetime

def _row_to_user(row: dict[str, Any]) -> User:
    return User(
        id=str(row["id"]),
        email=row["email"],
        name=row["name"],
        role=row["role"],
        password_hash=row["password_hash"],
        google_sub=row["google_sub"],
        is_active=row["is_active"],
        question_quota=row["question_quota"],
        share_conversations=row["share_conversations"],
        created_at=row["created_at"],
    )

_COLUMNS = (
    "id, email, name, role, password_hash, google_sub, is_active, question_quota, "
    "share_conversations, created_at"
)
_SELECT = f"SELECT {_COLUMNS} FROM users"

def normalize_email(raw: str) -> str:
    """Cắt khoảng trắng + hạ chữ thường.

    Áp NGAY TRONG tầng repo (không ở từng handler) vì có nhiều cửa cùng chạm email
    (/login, /register, /google, POST /api/admin/users) — sót một cửa là tài khoản nhân
    đôi hoặc không đăng nhập lại được (`TEXT UNIQUE` so byte nên `A@x.com` và `a@x.com`
    lọt thành 2 dòng). CỐ Ý không bỏ dấu chấm / phần `+tag`: đó là luật riêng của Gmail,
    áp cho domain khác sẽ gộp nhầm hai người thật sự khác nhau. Xem plan §4.4.
    """
    return raw.strip().lower()

def get_user_by_email(email: str) -> User | None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"{_SELECT} WHERE email = %s", (normalize_email(email),))
        row = cur.fetchone()
    return _row_to_user(row) if row else None

def get_user_by_id(user_id: str) -> User | None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"{_SELECT} WHERE id = %s", (user_id,))
        row = cur.fetchone()
    return _row_to_user(row) if row else None

def get_user_by_google_sub(google_sub: str) -> User | None:
    with connection() as conn, conn.cursor() as cur:
        cur.execute(f"{_SELECT} WHERE google_sub = %s", (google_sub,))
        row = cur.fetchone()
    return _row_to_user(row) if row else None

def create_user(
    email: str,
    name: str,
    role: Role,
    password_hash: str | None,
    google_sub: str | None = None,
) -> User:
    """`password_hash=None` + `google_sub` = tài khoản Google-only (không có mật khẩu)."""
    user_id = str(uuid.uuid4())
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"INSERT INTO users (id, email, name, role, password_hash, google_sub) "
            f"VALUES (%s, %s, %s, %s, %s, %s) RETURNING {_COLUMNS}",
            (user_id, normalize_email(email), name, role, password_hash, google_sub),
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
    """PATCH một phần (role/is_active/question_quota; name/password_hash từ /api/auth/me).
    `fields` đã lọc cột hợp lệ ở API — tên cột nối thẳng vào SQL."""
    if not fields:
        return get_user_by_id(user_id)
    set_clause = ", ".join(f"{col} = %s" for col in fields)
    params = [*fields.values(), user_id]
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE users SET {set_clause} WHERE id = %s RETURNING {_COLUMNS}",
            params,
        )
        row = cur.fetchone()
        conn.commit()
    return _row_to_user(row) if row else None

def set_share_conversations(user_id: str, enabled: bool) -> User | None:
    """Người dùng tự bật/tắt chia sẻ hội thoại; ghi kèm thời điểm đổi."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            f"UPDATE users SET share_conversations = %s, share_updated_at = now() "
            f"WHERE id = %s RETURNING {_COLUMNS}",
            (enabled, user_id),
        )
        row = cur.fetchone()
        conn.commit()
    return _row_to_user(row) if row else None

def flagged_counts() -> dict[str, int]:
    """Số câu hỏi bị guardrails gắn cờ vi phạm của từng user (user không có thì vắng mặt)."""
    with connection() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT c.user_id, count(*) AS n FROM messages m "
            "JOIN conversations c ON c.id = m.conversation_id "
            "WHERE m.flagged GROUP BY c.user_id"
        )
        rows = cur.fetchall()
    return {str(r["user_id"]): int(r["n"]) for r in rows}
