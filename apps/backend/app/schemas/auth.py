"""Request/response schema cho auth."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, EmailStr, Field, StringConstraints, field_validator

from app.core.security import validate_bcrypt_password
from app.schemas.common import Role

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    """Đăng ký công khai. KHÔNG có field `role` — role hardcode `"user"` trong handler;
    nhận role từ client là mở đường tự phong admin (plan §4.2)."""

    email: EmailStr
    name: str = Field(min_length=2, max_length=80)
    # min_length CỐ Ý cao hơn UserCreate (6): admin tạo hộ thì tự chịu trách nhiệm.
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def _fits_bcrypt(cls, v: str) -> str:
        return validate_bcrypt_password(v)

class GoogleLoginRequest(BaseModel):
    """`credential` = ID token (JWT do Google ký) mà nút "Sign in with Google" trả về.
    Backend chỉ verify chữ ký rồi cấp JWT của HỆ THỐNG MÌNH — Google là thêm một cửa vào,
    không phải hệ thống phiên thứ hai."""

    credential: str = Field(min_length=1)

class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: Role
    share_conversations: bool
    # False = tài khoản Google-only -> frontend ẩn mục "Đổi mật khẩu".
    has_password: bool

class PreferencesUpdate(BaseModel):
    share_conversations: bool

class ProfileUpdate(BaseModel):
    """Người dùng tự sửa hồ sơ. CHỈ có `name`: email là định danh đăng nhập (và gắn với
    tài khoản Google), hệ thống chưa xác minh email nên không cho tự đổi."""

    # strip trước khi đếm độ dài: "   " không được lọt thành tên rỗng.
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=80)]

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8)  # cùng ngưỡng với RegisterRequest

    @field_validator("new_password")
    @classmethod
    def _fits_bcrypt(cls, v: str) -> str:
        return validate_bcrypt_password(v)

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
