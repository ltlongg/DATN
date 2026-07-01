"""Schema cho Module 4 — Người dùng & quota (admin)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

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
    password: str = Field(min_length=6, max_length=200)


class UserUpdate(BaseModel):
    # PATCH: chỉ field được gửi mới cập nhật (exclude_unset ở API). question_quota=null hợp
    # lệ (đặt lại về không giới hạn).
    role: Role | None = None
    is_active: bool | None = None
    question_quota: int | None = Field(default=None, ge=0)
