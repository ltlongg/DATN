"""Unit test: password hashing + JWT (không cần DB)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

def test_hash_and_verify_password() -> None:
    h = hash_password("secret123")
    assert h != "secret123"
    assert verify_password("secret123", h)
    assert not verify_password("wrong", h)

def test_verify_password_bad_hash_returns_false() -> None:
    assert not verify_password("x", "not-a-bcrypt-hash")

def test_create_and_decode_token_roundtrip() -> None:
    token = create_access_token(user_id="u1", role="user")
    payload = decode_access_token(token)
    assert payload["sub"] == "u1"
    assert payload["role"] == "user"

def test_decode_expired_token_raises() -> None:
    settings = get_settings()
    expired = jwt.encode(
        {"sub": "u1", "role": "user", "exp": datetime.now(tz=timezone.utc) - timedelta(minutes=1)},
        settings.backend_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    with pytest.raises(TokenError):
        decode_access_token(expired)

def test_decode_garbage_token_raises() -> None:
    with pytest.raises(TokenError):
        decode_access_token("not.a.jwt")
