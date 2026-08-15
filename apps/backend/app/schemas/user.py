"""Schema cho Module 4 — Người dùng & quota (admin)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import validate_bcrypt_password
from app.schemas.common import Role

class UserOut(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: Role
    is_active: bool
    question_quota: int | None  # None = không giới hạn
    created_at: datetime

class UserCreate(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=200)
    role: Role
    # KHÔNG dùng max_length: bcrypt đếm BYTE, max_length đếm KÝ TỰ -> mật khẩu tiếng Việt
    # có dấu vẫn lọt qua rồi bị cắt im lặng. Xem security.validate_bcrypt_password.
    password: str = Field(min_length=6)

    @field_validator("password")
    @classmethod
    def _fits_bcrypt(cls, v: str) -> str:
        return validate_bcrypt_password(v)

class UserUpdate(BaseModel):
    # PATCH: chỉ field được gửi mới cập nhật (exclude_unset ở API). question_quota=null hợp
    # lệ (đặt lại về không giới hạn).
    role: Role | None = None
    is_active: bool | None = None
    question_quota: int | None = Field(default=None, ge=0)
