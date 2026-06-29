"""Request/response schema cho auth."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr

from app.schemas.common import Role


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    name: str
    role: Role


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic
