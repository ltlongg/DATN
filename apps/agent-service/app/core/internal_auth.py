"""Auth nội bộ service-to-service: header `X-Internal-Key` khớp `INTERNAL_API_KEY` (.env).

Agent-service KHÔNG có bảng `users` và KHÔNG xác thực người dùng — việc đó xong ở backend.
Lớp này chỉ trả lời một câu: "caller có phải service nội bộ của mình hay không". Bởi vậy
CỐ Ý không dùng JWT của user: token đó nằm trong tay user (localStorage) nên user tự gọi
thẳng :9000 được, đi vòng qua quota/`debug=False`/log ở backend. Xem CLAUDE.md §Architecture.

Dùng `APIKeyHeader` (thay vì tự đọc `Request.headers`) để scheme vào OpenAPI -> Swagger UI
`:9000/docs` có nút **Authorize**, dán key 1 lần là test được mọi endpoint.

Fail-closed 2 lớp: thiếu/sai key -> 401; server chưa cấu hình key -> 500. KHÔNG có nhánh
"key rỗng thì bỏ qua check" — đó là cách `.env` thiếu 1 dòng lúc deploy thành mở cửa im lặng.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException
from fastapi.security import APIKeyHeader

from app.core.config import get_settings

INTERNAL_KEY_HEADER = "X-Internal-Key"

# auto_error=False -> tự ném lỗi có body {code,message} thay vì 403 mặc định của FastAPI.
_key_header = APIKeyHeader(name=INTERNAL_KEY_HEADER, auto_error=False)


async def verify_internal_key(key: str | None = Depends(_key_header)) -> None:
    """Chặn request không mang đúng `X-Internal-Key`. Gắn ở cấp router (xem app/main.py)."""
    expected = get_settings().internal_api_key
    if not expected:
        # Lỗi cấu hình server, KHÔNG phải lỗi caller -> 500 để phân biệt khi debug deploy.
        raise HTTPException(
            status_code=500,
            detail={
                "code": "internal_key_not_configured",
                "message": "Server chưa cấu hình INTERNAL_API_KEY.",
            },
        )
    # compare_digest: so khớp thời gian hằng định, không rò rỉ độ dài prefix trùng qua timing.
    if not key or not secrets.compare_digest(key, expected):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "unauthenticated",
                "message": f"Thiếu hoặc sai header {INTERNAL_KEY_HEADER}.",
            },
        )


def internal_headers() -> dict[str, str]:
    """Header để GỬI khi agent-service gọi ngược backend (`GET /internal/config`).

    Key rỗng -> trả dict rỗng thay vì header rỗng: để backend trả 401 rõ ràng, và tránh
    gửi `X-Internal-Key: ""` gây nhầm lẫn khi đọc log.
    """
    key = get_settings().internal_api_key
    return {INTERNAL_KEY_HEADER: key} if key else {}
