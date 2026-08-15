"""Auth nội bộ service-to-service phía backend: header `X-Internal-Key`.

Đối xứng `agent-service/app/core/internal_auth.py` (cùng tên header, cùng `INTERNAL_API_KEY`
trong root `.env`), nhưng khác VAI: file này gác `/internal/*` — endpoint agent-service GỌI
VÀO — còn `services/agent_client.py` lo phần GỬI key khi backend gọi ra.

Vì sao không dùng JWT ở tầng này: JWT trả lời "user nào" và nằm trong tay user
(localStorage), nên user tự gọi thẳng service nội bộ được. Key này trả lời "service nào" và
chỉ 2 process đọc `.env` mới có. Xem CLAUDE.md §Architecture.

Lỗi ném bằng `AppError` (không phải `HTTPException`) để đi qua handler chung ->
body `{code,message}` + `request.state.error_code` cho ActivityLogMiddleware. Fail-closed:
key rỗng -> 500, thiếu/sai -> 401. KHÔNG có nhánh "rỗng thì bỏ qua".
"""

from __future__ import annotations

import secrets

from fastapi import Depends
from fastapi.security import APIKeyHeader

from app.core.config import get_settings
from app.core.errors import AppError

INTERNAL_KEY_HEADER = "X-Internal-Key"

_key_header = APIKeyHeader(name=INTERNAL_KEY_HEADER, auto_error=False)

async def verify_internal_key(key: str | None = Depends(_key_header)) -> None:
    """Chặn request `/internal/*` không mang đúng `X-Internal-Key` (gắn ở api/internal.py)."""
    expected = get_settings().internal_api_key
    if not expected:
        raise AppError(
            500, "internal_key_not_configured", "Server chưa cấu hình INTERNAL_API_KEY."
        )
    if not key or not secrets.compare_digest(key, expected):
        raise AppError(401, "unauthenticated", f"Thiếu hoặc sai header {INTERNAL_KEY_HEADER}.")

def internal_headers() -> dict[str, str]:
    """Header để GỬI khi backend gọi agent-service (`/ask`, `/kb/*`).

    Key rỗng -> dict rỗng: agent trả 401 rõ ràng thay vì nhận header rỗng khó đọc trong log.
    """
    key = get_settings().internal_api_key
    return {INTERNAL_KEY_HEADER: key} if key else {}
