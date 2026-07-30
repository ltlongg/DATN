"""API test: register / login / google / me / logout."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from google.auth.exceptions import TransportError


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Thay `verify_oauth2_token` bằng hàm giả — KHÔNG bao giờ gọi mạng thật trong test.

    Trả về `configure(...)` để mỗi test đặt payload (hoặc exception) Google "trả về".
    """
    from app.api import auth as auth_api
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "google_client_id", "test-client-id")

    state: dict[str, Any] = {
        "sub": "sub-mac-dinh",
        "email": "gg-zz@example.com",
        "name": "Gờ Gờ",
        "email_verified": True,
        "exc": None,
    }

    def fake_verify(credential: str, request: object, audience: str) -> dict[str, Any]:
        if state["exc"] is not None:
            raise state["exc"]
        return {
            "sub": state["sub"],
            "email": state["email"],
            "email_verified": state["email_verified"],
            "name": state["name"],
        }

    monkeypatch.setattr(auth_api.id_token, "verify_oauth2_token", fake_verify)

    def configure(**kwargs: Any) -> None:
        state.update(kwargs)

    return configure


def _google_login(client: TestClient):  # type: ignore[no-untyped-def]
    return client.post("/api/auth/google", json={"credential": "id-token-gia"})


def _register(client: TestClient, email: str, **extra: object):  # type: ignore[no-untyped-def]
    body: dict[str, object] = {"email": email, "name": "Người Mới", "password": "secret123"}
    body.update(extra)
    return client.post("/api/auth/register", json=body)


# --- register ---------------------------------------------------------------


def test_register_success_returns_usable_token(client: TestClient, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = _register(client, "moi-zz@example.com")
    assert r.status_code == 201
    body = r.json()
    assert body["user"]["role"] == "user"
    # Token cấp ngay -> auto-login, không bắt gõ lại mật khẩu vừa đặt.
    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["email"] == "moi-zz@example.com"


def test_register_duplicate_email_409(client: TestClient, db_conn) -> None:  # type: ignore[no-untyped-def]
    _register(client, "trung-zz@example.com")
    r = _register(client, "trung-zz@example.com")
    assert r.status_code == 409
    assert r.json()["code"] == "email_taken"


def test_register_short_password_422(client: TestClient, db_conn) -> None:  # type: ignore[no-untyped-def]
    assert _register(client, "ngan-zz@example.com", password="1234567").status_code == 422


def test_register_password_over_72_bytes_422(client: TestClient, db_conn) -> None:  # type: ignore[no-untyped-def]
    # 72 KÝ TỰ tiếng Việt có dấu = 144 byte > giới hạn bcrypt -> phải từ chối, KHÔNG cắt
    # im lặng (mật khẩu ngắn hơn người dùng tưởng).
    r = _register(client, "dai-zz@example.com", password="á" * 72)
    assert r.status_code == 422


def test_register_ignores_role_in_body(client: TestClient, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = _register(client, "tu-phong-zz@example.com", role="admin")
    assert r.status_code == 201
    assert r.json()["user"]["role"] == "user"


# --- chuẩn hoá email (plan §4.4) --------------------------------------------


def test_register_then_login_ignores_email_case(client: TestClient, db_conn) -> None:  # type: ignore[no-untyped-def]
    _register(client, "Hoa-ZZ@Example.com", password="secret123")
    r = client.post(
        "/api/auth/login", json={"email": "hoa-zz@example.com", "password": "secret123"}
    )
    assert r.status_code == 200


def test_register_duplicate_email_other_case_409(client: TestClient, db_conn) -> None:  # type: ignore[no-untyped-def]
    _register(client, "Case-ZZ@Example.com")
    r = _register(client, "case-zz@example.com")
    assert r.status_code == 409
    assert r.json()["code"] == "email_taken"


def test_register_strips_whitespace_in_email(client: TestClient, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = _register(client, "  khoangtrang-zz@example.com  ")
    assert r.status_code == 201
    assert r.json()["user"]["email"] == "khoangtrang-zz@example.com"


# --- login / me / logout ----------------------------------------------------


def test_login_success(client: TestClient, users: dict[str, object]) -> None:
    r = client.post(
        "/api/auth/login", json={"email": "user-test@example.com", "password": "userpw"}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["email"] == "user-test@example.com"
    assert body["user"]["role"] == "user"


def test_login_wrong_password(client: TestClient, users: dict[str, object]) -> None:
    r = client.post(
        "/api/auth/login", json={"email": "user-test@example.com", "password": "WRONG"}
    )
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"


def test_login_unknown_email(client: TestClient, users: dict[str, object]) -> None:
    r = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "x"})
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"


def test_me_returns_current_user(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/auth/me", headers=auth("user"))
    assert r.status_code == 200
    assert r.json()["email"] == "user-test@example.com"


def test_me_requires_token(client: TestClient) -> None:
    r = client.get("/api/auth/me")
    assert r.status_code == 401
    assert r.json()["code"] == "unauthenticated"


def test_me_rejects_bad_token(client: TestClient) -> None:
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


def test_logout(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/auth/logout", headers=auth("user"))
    assert r.status_code == 200
    assert r.json()["ok"] is True


# --- đăng nhập Google (plan §4.3.3) -----------------------------------------


def test_google_first_login_creates_user(client: TestClient, google, db_conn) -> None:  # type: ignore[no-untyped-def]
    google(sub="sub-moi-zz", email="moi-gg-zz@example.com", name="Người Google")
    r = _google_login(client)
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["role"] == "user"
    assert body["user"]["email"] == "moi-gg-zz@example.com"
    assert body["user"]["name"] == "Người Google"
    me = client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200


def test_google_second_login_same_sub_reuses_user(client: TestClient, google, db_conn) -> None:  # type: ignore[no-untyped-def]
    google(sub="sub-lap-zz", email="lap-zz@example.com")
    first = _google_login(client).json()["user"]["id"]
    second = _google_login(client).json()["user"]["id"]
    assert first == second


def test_google_falls_back_to_email_prefix_when_no_name(client: TestClient, google, db_conn) -> None:  # type: ignore[no-untyped-def]
    google(sub="sub-khongten-zz", email="khongten-zz@example.com", name=None)
    assert _google_login(client).json()["user"]["name"] == "khongten-zz"


def test_google_invalid_token_401(client: TestClient, google, db_conn) -> None:  # type: ignore[no-untyped-def]
    google(exc=ValueError("token hết hạn"))
    r = _google_login(client)
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_google_token"


def test_google_transport_error_503_not_401(client: TestClient, google, db_conn) -> None:  # type: ignore[no-untyped-def]
    # TransportError kế thừa GoogleAuthError -> đảo thứ tự except là Google sập bị báo
    # thành "token không hợp lệ" (đổ lỗi cho người dùng). Cũng không được thành 500 trần.
    google(exc=TransportError("không tải được cert"))
    r = _google_login(client)
    assert r.status_code == 503
    assert r.json()["code"] == "google_unavailable"


def test_google_unverified_email_401(client: TestClient, google, db_conn) -> None:  # type: ignore[no-untyped-def]
    google(sub="sub-chuaxacminh-zz", email="chua-zz@example.com", email_verified=False)
    r = _google_login(client)
    assert r.status_code == 401
    assert r.json()["code"] == "google_email_unverified"


def test_google_locked_account_403(client: TestClient, google, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    # Nếu quên nhánh is_active, tài khoản bị admin khóa vẫn vào được bằng cửa Google.
    google(sub="sub-khoa-zz", email="khoa-gg-zz@example.com")
    uid = _google_login(client).json()["user"]["id"]
    client.patch(f"/api/admin/users/{uid}", json={"is_active": False}, headers=auth("admin"))
    r = _google_login(client)
    assert r.status_code == 403
    assert r.json()["code"] == "account_locked"


def test_google_does_not_link_to_existing_password_account(client: TestClient, google, db_conn) -> None:  # type: ignore[no-untyped-def]
    """Chốt lỗ hổng pre-hijacking: KHÔNG tự ghép Google vào tài khoản mật khẩu cùng email."""
    _register(client, "nan-nhan-zz@example.com")
    google(sub="sub-ke-xau-zz", email="nan-nhan-zz@example.com")

    r = _google_login(client)
    assert r.status_code == 409
    assert r.json()["code"] == "account_link_required"

    # Và KHÔNG âm thầm ghi google_sub vào tài khoản đó.
    with db_conn.cursor() as cur:
        cur.execute(
            "SELECT google_sub FROM users WHERE email = %s", ("nan-nhan-zz@example.com",)
        )
        assert cur.fetchone()["google_sub"] is None


def test_google_login_disabled_when_client_id_missing(client: TestClient, google, db_conn) -> None:  # type: ignore[no-untyped-def]
    from app.core.config import get_settings

    get_settings().google_client_id = ""  # monkeypatch của fixture `google` sẽ khôi phục
    r = _google_login(client)
    assert r.status_code == 503
    assert r.json()["code"] == "google_login_disabled"


def test_google_only_account_cannot_login_with_password(client: TestClient, google, db_conn) -> None:  # type: ignore[no-untyped-def]
    # password_hash NULL -> verify_password trả False -> đúng message invalid_credentials,
    # KHÔNG lộ "tài khoản này đăng nhập bằng Google".
    google(sub="sub-khongmk-zz", email="khongmk-zz@example.com")
    _google_login(client)
    r = client.post(
        "/api/auth/login", json={"email": "khongmk-zz@example.com", "password": "doan-bua"}
    )
    assert r.status_code == 401
    assert r.json()["code"] == "invalid_credentials"
