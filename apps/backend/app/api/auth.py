"""Auth router — login / me / logout.

JWT stateless: logout chỉ là no-op phía server (client xóa token). Không có refresh/
revoke ở MVP (xem "Sau MVP" trong backend-plan.md).
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.errors import AppError
from app.core.security import create_access_token, verify_password
from app.models.user import User, get_user_by_email
from app.schemas.auth import LoginRequest, LoginResponse, UserPublic
from app.schemas.common import OkResponse

router = APIRouter()


def _to_public(user: User) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, name=user.name, role=user.role)


@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    user = await anyio.to_thread.run_sync(get_user_by_email, str(body.email))
    # Cùng một message cho "không có email" và "sai mật khẩu" để không lộ email tồn tại.
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Email hoặc mật khẩu không đúng.")
    token = create_access_token(user_id=user.id, role=user.role)
    return LoginResponse(access_token=token, user=_to_public(user))


@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)) -> UserPublic:
    return _to_public(user)


@router.post("/logout", response_model=OkResponse)
async def logout(_: User = Depends(get_current_user)) -> OkResponse:
    return OkResponse()
