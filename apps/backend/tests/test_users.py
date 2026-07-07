"""Module 4 — Người dùng & quota: CRUD admin, gác admin, email trùng 409, self-lock,
khóa tài khoản (login + token cũ), quota (regression off-by-one câu đầu).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.agent_client import format_sse

_DONE = format_sse("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})


def _create_user(client: TestClient, admin_h, email, *, role="teacher", password="secret123"):  # type: ignore[no-untyped-def]
    return client.post(
        "/api/admin/users",
        json={"email": email, "name": "U", "role": role, "password": password},
        headers=admin_h,
    )


# --- CRUD -------------------------------------------------------------------


def test_create_user_defaults(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = _create_user(client, auth("admin"), "new-zz@example.com")
    assert r.status_code == 201
    body = r.json()
    assert body["is_active"] is True
    assert body["question_quota"] is None  # mặc định không giới hạn


def test_create_user_duplicate_email_409(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    admin = auth("admin")
    _create_user(client, admin, "dup-zz@example.com")
    r = _create_user(client, admin, "dup-zz@example.com")
    assert r.status_code == 409
    assert r.json()["code"] == "conflict"


def test_list_users_contains_created(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    _create_user(client, auth("admin"), "listed-zz@example.com")
    r = client.get("/api/admin/users", headers=auth("admin"))
    assert r.status_code == 200
    assert "listed-zz@example.com" in [u["email"] for u in r.json()]


def test_patch_user_role_and_quota(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    uid = _create_user(client, auth("admin"), "patch-zz@example.com").json()["id"]
    r = client.patch(
        f"/api/admin/users/{uid}",
        json={"role": "admin", "question_quota": 5},
        headers=auth("admin"),
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"
    assert r.json()["question_quota"] == 5


def test_patch_user_404(client, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.patch(
        "/api/admin/users/00000000-0000-0000-0000-000000000000",
        json={"is_active": False},
        headers=auth("admin"),
    )
    assert r.status_code == 404


# --- guards -----------------------------------------------------------------


def test_users_require_admin(client, auth) -> None:  # type: ignore[no-untyped-def]
    assert client.get("/api/admin/users", headers=auth("teacher")).status_code == 403


def test_admin_cannot_self_lock(client, auth, db_conn, users) -> None:  # type: ignore[no-untyped-def]
    admin_id = users["admin"].id
    r = client.patch(
        f"/api/admin/users/{admin_id}", json={"is_active": False}, headers=auth("admin")
    )
    assert r.status_code == 400
    assert r.json()["code"] == "self_lock_forbidden"


def test_admin_cannot_self_demote(client, auth, db_conn, users) -> None:  # type: ignore[no-untyped-def]
    admin_id = users["admin"].id
    r = client.patch(
        f"/api/admin/users/{admin_id}", json={"role": "teacher"}, headers=auth("admin")
    )
    assert r.status_code == 400
    assert r.json()["code"] == "self_demote_forbidden"


def test_admin_can_demote_another_admin(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    # Hạ quyền admin KHÁC vẫn cho phép (chỉ chặn tự hạ quyền chính mình).
    uid = _create_user(client, auth("admin"), "other-admin-zz@example.com", role="admin").json()[
        "id"
    ]
    r = client.patch(
        f"/api/admin/users/{uid}", json={"role": "teacher"}, headers=auth("admin")
    )
    assert r.status_code == 200
    assert r.json()["role"] == "teacher"


# --- account lock -----------------------------------------------------------


def test_locked_account_cannot_login_or_use_old_token(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    admin = auth("admin")
    email, pw = "lock-zz@example.com", "secret123"
    uid = _create_user(client, admin, email, password=pw).json()["id"]
    # token cũ còn hạn (login khi còn active)
    old_token = client.post(
        "/api/auth/login", json={"email": email, "password": pw}
    ).json()["access_token"]
    # admin khóa tài khoản
    client.patch(f"/api/admin/users/{uid}", json={"is_active": False}, headers=admin)
    # login lại -> 403 account_locked (KHÔNG cấp token mới)
    relogin = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert relogin.status_code == 403
    assert relogin.json()["code"] == "account_locked"
    # token cũ còn hạn -> vẫn 403 ở get_current_user
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"})
    assert me.status_code == 403
    assert me.json()["code"] == "account_locked"


# --- quota ------------------------------------------------------------------


def test_quota_first_question_ok_second_blocked(client, auth, mock_agent, db_conn) -> None:  # type: ignore[no-untyped-def]
    admin = auth("admin")
    email, pw = "quota-zz@example.com", "secret123"
    uid = _create_user(client, admin, email, password=pw).json()["id"]
    client.patch(f"/api/admin/users/{uid}", json={"question_quota": 1}, headers=admin)
    token = client.post(
        "/api/auth/login", json={"email": email, "password": pw}
    ).json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    cid = client.post("/api/chat/conversations", json={}, headers=h).json()["id"]

    mock_agent.configure(events=format_sse("token", {"text": "ok"}) + _DONE)
    r1 = client.post(f"/api/chat/conversations/{cid}/ask", json={"question": "Q1"}, headers=h)
    assert r1.status_code == 200  # câu ĐẦU trong ngày phải thành công (regression off-by-one)

    mock_agent.configure(events=format_sse("token", {"text": "ok"}) + _DONE)
    r2 = client.post(f"/api/chat/conversations/{cid}/ask", json={"question": "Q2"}, headers=h)
    assert r2.status_code == 429
    assert r2.json()["code"] == "quota_exceeded"

    # message câu bị chặn KHÔNG được lưu (chỉ Q1).
    detail = client.get(f"/api/chat/conversations/{cid}", headers=h).json()
    assert [m["content"] for m in detail["messages"] if m["role"] == "user"] == ["Q1"]
