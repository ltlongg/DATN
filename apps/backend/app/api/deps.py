"""FastAPI dependencies dùng chung: lấy user hiện tại từ JWT + role guard.

`get_current_user` đọc Bearer token -> decode -> nạp user. `require_admin` chặn non-admin.
Lỗi auth dùng AppError -> handler trả body {code,message} chuẩn.
"""

from __future__ import annotations

import anyio
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.errors import AppError
from app.core.security import TokenError, decode_access_token
from app.models.conversation import Conversation, get_conversation
from app.models.user import User, get_user_by_id

# auto_error=False -> tự xử lý thiếu header để trả body chuẩn thay vì 403 mặc định.
_bearer = HTTPBearer(auto_error=False)

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> User:
    if credentials is None:
        raise AppError(401, "unauthenticated", "Thiếu token xác thực.")
    try:
        payload = decode_access_token(credentials.credentials)
    except TokenError:
        raise AppError(401, "unauthenticated", "Token không hợp lệ hoặc đã hết hạn.")

    user = await anyio.to_thread.run_sync(get_user_by_id, str(payload["sub"]))
    if user is None:
        raise AppError(401, "unauthenticated", "Tài khoản không tồn tại.")
    # Chặn ở MỌI request có token -> khóa có hiệu lực ngay cả với token cũ còn hạn.
    if not user.is_active:
        raise AppError(403, "account_locked", "Tài khoản đã bị khóa.")
    return user

async def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise AppError(403, "forbidden", "Chỉ admin được phép truy cập.")
    return user

async def get_owned_conversation(
    conversation_id: str, user: User = Depends(get_current_user)
) -> Conversation:
    """Nạp conversation và bảo đảm user là chủ sở hữu (hoặc admin). 404 nếu không có,
    403 nếu không phải của mình."""
    conv = await anyio.to_thread.run_sync(get_conversation, conversation_id)
    if conv is None:
        raise AppError(404, "not_found", "Không tìm thấy cuộc trò chuyện.")
    if conv.user_id != user.id and user.role != "admin":
        raise AppError(403, "forbidden", "Không có quyền truy cập cuộc trò chuyện này.")
    return conv
