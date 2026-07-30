"""API test: login / me / logout."""

from __future__ import annotations

from fastapi.testclient import TestClient


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
