"""Module 4 — Người dùng & quota router (admin) — prefix /api/admin/users.

CRUD tối thiểu: list, tạo (hash password), PATCH role/is_active/question_quota. Guard:
admin không tự khóa (self_lock_forbidden) và không tự hạ quyền chính mình
(self_demote_forbidden). Xem backend-additions-plan.md §3.2.
"""

from __future__ import annotations

import anyio
import psycopg
from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.core.errors import AppError
from app.core.security import hash_password
from app.models import user as user_repo
from app.models.user import User
from app.schemas.user import UserCreate, UserOut, UserUpdate

router = APIRouter(dependencies=[Depends(require_admin)])

def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        name=user.name,
        role=user.role,
        is_active=user.is_active,
        question_quota=user.question_quota,
        created_at=user.created_at,
    )

@router.get("", response_model=list[UserOut])
async def list_users() -> list[UserOut]:
    users = await anyio.to_thread.run_sync(user_repo.list_users)
    return [_to_out(u) for u in users]

@router.post("", response_model=UserOut, status_code=201)
async def create_user(body: UserCreate) -> UserOut:
    try:
        user = await anyio.to_thread.run_sync(
            lambda: user_repo.create_user(
                str(body.email), body.name, body.role, hash_password(body.password)
            )
        )
    except psycopg.errors.UniqueViolation:
        raise AppError(409, "conflict", "Email đã tồn tại.")
    return _to_out(user)

@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str, body: UserUpdate, admin: User = Depends(require_admin)
) -> UserOut:
    fields = body.model_dump(exclude_unset=True)
    # Guard tự khóa: admin không được đặt is_active=False cho CHÍNH MÌNH (tránh mất quyền).
    if user_id == admin.id and fields.get("is_active") is False:
        raise AppError(400, "self_lock_forbidden", "Không thể tự khóa tài khoản của mình.")
    # Guard tự hạ quyền: admin không được đổi role của CHÍNH MÌNH sang non-admin
    # (tránh lặp lại sự cố tự khóa mình ra khỏi khu quản trị).
    if user_id == admin.id and fields.get("role") not in (None, "admin"):
        raise AppError(400, "self_demote_forbidden", "Không thể tự hạ quyền admin của mình.")
    user = await anyio.to_thread.run_sync(user_repo.update_user, user_id, fields)
    if user is None:
        raise AppError(404, "not_found", "Không tìm thấy người dùng.")
    return _to_out(user)
