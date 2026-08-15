"""Lỗi chuẩn hóa cho backend: body luôn `{"code": ..., "message": ...}` (không lộ
stack/secret cho frontend — backend-plan.md "Error Handling").

`AppError` là exception nghiệp vụ ném từ service/api; handler dưới đây map nó (và các
lỗi FastAPI mặc định) về cùng một body. Đăng ký handler trong `main.py`.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

class AppError(Exception):
    """Lỗi nghiệp vụ có status + code + message an toàn để trả frontend."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

# Code mặc định theo status, dùng cho HTTPException(detail=str) hoặc lỗi framework.
_DEFAULT_CODE: dict[int, str] = {
    400: "bad_request",
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    422: "validation_error",
    500: "internal_error",
    502: "agent_bad_response",
    503: "dependency_unavailable",
    504: "timeout",
}

def _body(code: str, message: str) -> dict[str, str]:
    return {"code": code, "message": message}

def register_error_handlers(app: FastAPI) -> None:
    # Mỗi handler ghi `code` lên request.state để ActivityLogMiddleware đọc lại sau call_next
    # (nó chỉ thấy response, không thấy exception đã bị handler nuốt). Xem activity-log-plan §4.3.
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        request.state.error_code = exc.code
        return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message))

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # detail có thể là dict {code,message} (ta tự ném) hoặc str (mặc định FastAPI).
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail:
            code = str(detail.get("code"))
            message = str(detail.get("message", ""))
        else:
            code = _DEFAULT_CODE.get(exc.status_code, "error")
            message = str(detail)
        request.state.error_code = code
        return JSONResponse(status_code=exc.status_code, content=_body(code, message))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Gộp lỗi đầu tiên cho gọn — frontend MVP chỉ cần message hiển thị được.
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(p) for p in first.get("loc", []) if p != "body")
        msg = first.get("msg", "Dữ liệu không hợp lệ.")
        # Pydantic v2 chèn "Value error, " / "Assertion failed, " trước message của validator
        # mình viết. Message đó đã là câu tiếng Việt đủ ngữ cảnh ("Mật khẩu quá dài, tối đa 72
        # byte.") -> bỏ tiền tố rác + bỏ luôn tên field tiếng Anh (`password:`). Lỗi framework
        # còn lại (type/thiếu field) vẫn giữ `loc` để biết field nào sai.
        message = None
        for prefix in ("Value error, ", "Assertion failed, "):
            if msg.startswith(prefix):
                message = msg[len(prefix) :]
                break
        if message is None:
            message = f"{loc}: {msg}" if loc else msg
        request.state.error_code = "validation_error"
        return JSONResponse(status_code=422, content=_body("validation_error", message))
