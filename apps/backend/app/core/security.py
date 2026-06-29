"""Password hashing (bcrypt) + JWT access token (PyJWT).

Dùng bcrypt trực tiếp (không qua passlib — passlib không tương thích bcrypt 4/5) và
PyJWT (gọn hơn python-jose). JWT payload: {"sub": user_id, "role": ..., "exp", "iat"}
theo backend-plan.md.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import get_settings

# bcrypt chỉ dùng 72 byte đầu của mật khẩu; cắt cho nhất quán giữa hash và verify
# (mật khẩu dài hơn 72 byte sẽ không bị bcrypt 5.x ném lỗi).
_BCRYPT_MAX_BYTES = 72


def _prepared(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepared(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(_prepared(password), password_hash.encode("utf-8"))
    except ValueError:
        # password_hash rỗng / sai format -> coi như không khớp, không raise.
        return False


class TokenError(Exception):
    """Token thiếu/hết hạn/sai chữ ký — api layer map về 401."""


def create_access_token(user_id: str, role: str) -> str:
    settings = get_settings()
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.backend_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, object]:
    """Giải mã + kiểm hạn token. Ném TokenError nếu hết hạn / sai chữ ký / thiếu sub."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.backend_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    if "sub" not in payload:
        raise TokenError("Token thiếu trường sub.")
    return payload
