"""Type/schema dùng chung."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Role = Literal["admin", "user"]

class ErrorResponse(BaseModel):
    """Body lỗi chuẩn (khớp core/errors.py) — khai báo để hiện trong OpenAPI."""

    code: str
    message: str

class OkResponse(BaseModel):
    ok: bool = True
