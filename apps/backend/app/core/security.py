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

# bcrypt chỉ dùng 72 BYTE đầu của mật khẩu (không phải 72 ký tự — tiếng Việt có dấu
# tốn 2-3 byte/ký tự).
_BCRYPT_MAX_BYTES = 72

def validate_bcrypt_password(password: str) -> str:
    """Từ chối mật khẩu vượt giới hạn bcrypt thay vì cắt im lặng.

    Cắt im lặng nghĩa là: đặt mật khẩu 80 byte, hệ thống chỉ lưu 72 byte đầu, người dùng
    gõ đúng 72 byte đầu CŨNG đăng nhập được — mật khẩu ngắn hơn họ tưởng mà không ai báo.
    Từ chối thẳng thì người dùng biết mà đổi. Gọi ở cả `RegisterRequest`, `UserCreate`
    (cửa admin) và `hash_password` (lớp phòng thủ cuối) — xem auth-landing-plan.md §4.2.
    """
    if len(password.encode("utf-8")) > _BCRYPT_MAX_BYTES:
        raise ValueError(f"Mật khẩu quá dài, tối đa {_BCRYPT_MAX_BYTES} byte.")
    return password

def hash_password(password: str) -> str:
    validate_bcrypt_password(password)
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(password: str, password_hash: str | None) -> bool:
    # None = tài khoản Google-only (không có mật khẩu) -> không khớp gì cả.
    if password_hash is None:
        return False
    # CỐ Ý vẫn cắt ở khâu verify (khác hash_password): hash cũ trong DB được sinh từ bản
    # đã cắt, bỏ cắt ở đây là khóa cửa chính những tài khoản đó. Validate chặn ở đầu vào,
    # không đụng đường đối chiếu.
    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:_BCRYPT_MAX_BYTES], password_hash.encode("utf-8")
        )
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
