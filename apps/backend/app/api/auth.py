"""Auth router — register / login / google / me / logout.

JWT stateless: logout chỉ là no-op phía server (client xóa token). Không có refresh/
revoke ở MVP (xem "Sau MVP" trong backend-plan.md).

Đăng ký công khai: ai đăng ký cũng thành `role="user"`, `is_active=true`, được cấp token
luôn (auto-login) — không có bước admin duyệt. Xem auth-landing-plan.md §2 Q1.

Google: luồng ID token (Google Identity Services), KHÔNG phải Authorization Code redirect
-> không cần client secret, redirect URI, hay state/PKCE. Xem plan §2 Q3 + §4.3.
"""

from __future__ import annotations

from typing import Any

import anyio
import cachecontrol
import psycopg
import requests
from fastapi import APIRouter, Depends
from google.auth.exceptions import GoogleAuthError, TransportError
from google.auth.transport import requests as ga_requests
from google.oauth2 import id_token

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User, create_user, get_user_by_email, get_user_by_google_sub
from app.schemas.auth import (
    GoogleLoginRequest,
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserPublic,
)
from app.schemas.common import OkResponse

router = APIRouter()

# google-auth KHÔNG tự cache cert: docs ghi rõ "By default, this will re-fetch certificates
# for each verification". Tái dùng Request() chỉ tái dùng TCP connection, không cache. Bọc
# CacheControl (đọc header Cache-Control của Google) mới hết round-trip mỗi lần đăng nhập.
_GA_REQUEST = ga_requests.Request(session=cachecontrol.CacheControl(requests.Session()))

def _to_public(user: User) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, name=user.name, role=user.role)

def _issue_token(user: User) -> LoginResponse:
    return LoginResponse(
        access_token=create_access_token(user_id=user.id, role=user.role),
        user=_to_public(user),
    )

@router.post("/register", response_model=LoginResponse, status_code=201)
async def register(body: RegisterRequest) -> LoginResponse:
    # role hardcode "user": KHÔNG bao giờ đọc từ body (RegisterRequest cũng không có field
    # đó) — đây là khác biệt bản chất so với POST /api/admin/users, nơi role đến từ body
    # nhưng đã có require_admin chắn.
    password_hash = hash_password(body.password)
    try:
        user = await anyio.to_thread.run_sync(
            create_user, str(body.email), body.name, "user", password_hash
        )
    except psycopg.errors.UniqueViolation:
        raise AppError(409, "email_taken", "Email này đã được đăng ký.")
    return _issue_token(user)

@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest) -> LoginResponse:
    user = await anyio.to_thread.run_sync(get_user_by_email, str(body.email))
    # Cùng một message cho "không có email" và "sai mật khẩu" để không lộ email tồn tại.
    if user is None or not verify_password(body.password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Email hoặc mật khẩu không đúng.")
    # login KHÔNG đi qua get_current_user -> phải check is_active ở ĐÂY nữa, nếu không tài
    # khoản bị khóa vẫn được cấp token mới (dù request kế tiếp sẽ 403). Check ở CẢ 2 chỗ.
    if not user.is_active:
        raise AppError(403, "account_locked", "Tài khoản đã bị khóa.")
    return _issue_token(user)

def _verify_google_credential(credential: str, client_id: str) -> dict[str, Any]:
    """Verify ID token. `verify_oauth2_token` tự kiểm chữ ký, `aud`, `exp`, `iss`.
    Blocking (phát HTTP lấy cert) -> luôn gọi qua anyio.to_thread."""
    return id_token.verify_oauth2_token(credential, _GA_REQUEST, client_id)

def _create_google_user(google_sub: str, email: str, idinfo: dict[str, Any]) -> User:
    """Tạo tài khoản Google-only. KHÔNG tự ghép vào tài khoản mật khẩu cùng email.

    `email_verified=true` chỉ chứng minh GOOGLE tin email đó, KHÔNG chứng minh tài khoản
    local cùng email là của cùng một người — mà /register thì mở và không xác minh email.
    Tự ghép = kẻ xấu đăng ký trước bằng email nạn nhân sẽ giữ được quyền đọc dữ liệu nạn
    nhân bằng mật khẩu nó tự đặt (pre-hijacking). Liên kết Google vào tài khoản có sẵn là
    NỢ, cần trang cá nhân + đăng nhập bằng mật khẩu trước. Xem plan §4.3.3.
    """
    if get_user_by_email(email) is not None:
        raise AppError(
            409,
            "account_link_required",
            "Email này đã đăng ký bằng mật khẩu. Hãy đăng nhập bằng mật khẩu.",
        )
    name = str(idinfo.get("name") or email.split("@")[0])
    try:
        return create_user(email, name, "user", None, google_sub=google_sub)
    except psycopg.errors.UniqueViolation:
        # Race: 2 request đầu tiên của cùng một `sub` cùng qua được bước tra ở trên rồi
        # cùng INSERT. Đọc lại thay vì trả 500 — người thua cuộc vẫn đăng nhập được.
        existing = get_user_by_google_sub(google_sub)
        if existing is None:
            raise
        return existing

@router.post("/google", response_model=LoginResponse)
async def google_login(body: GoogleLoginRequest) -> LoginResponse:
    client_id = get_settings().google_client_id
    if not client_id:
        raise AppError(
            503, "google_login_disabled", "Đăng nhập Google chưa được cấu hình."
        )

    try:
        idinfo = await anyio.to_thread.run_sync(
            _verify_google_credential, body.credential, client_id
        )
    # THỨ TỰ KHÔNG ĐƯỢC ĐẢO: TransportError kế thừa GoogleAuthError. Bắt GoogleAuthError
    # trước là nuốt luôn lỗi mạng -> Google sập bị báo thành "token không hợp lệ", tức đổ
    # lỗi cho người dùng vì sự cố phía Google.
    except TransportError:
        raise AppError(
            503, "google_unavailable", "Google tạm thời không phản hồi. Vui lòng thử lại."
        )
    except (ValueError, GoogleAuthError):
        raise AppError(
            401, "invalid_google_token", "Thông tin đăng nhập Google không hợp lệ."
        )

    if idinfo.get("email_verified") is not True:
        raise AppError(
            401, "google_email_unverified", "Email Google chưa được xác minh."
        )
    google_sub = str(idinfo["sub"])
    email = str(idinfo["email"])

    user = await anyio.to_thread.run_sync(get_user_by_google_sub, google_sub)
    if user is None:
        user = await anyio.to_thread.run_sync(_create_google_user, google_sub, email, idinfo)
    if not user.is_active:
        raise AppError(403, "account_locked", "Tài khoản đã bị khóa.")
    return _issue_token(user)

@router.get("/me", response_model=UserPublic)
async def me(user: User = Depends(get_current_user)) -> UserPublic:
    return _to_public(user)

@router.post("/logout", response_model=OkResponse)
async def logout(_: User = Depends(get_current_user)) -> OkResponse:
    return OkResponse()
