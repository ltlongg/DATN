"""API test: role guard admin + ownership conversation."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_teacher_blocked_on_admin_documents(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    teacher = auth("teacher")
    assert client.get("/api/admin/documents", headers=teacher).status_code == 403
    assert client.post("/api/admin/documents", json={"name": "x"}, headers=teacher).status_code == 403


def test_admin_allowed_on_admin_documents(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/admin/documents", headers=auth("admin"))
    assert r.status_code == 200


def test_admin_routes_require_auth(client: TestClient) -> None:
    assert client.get("/api/admin/documents").status_code == 401


def test_conversation_ownership_blocks_other_teacher(
    client: TestClient, auth, users  # type: ignore[no-untyped-def]
) -> None:
    from app.core.security import hash_password
    from app.models.user import create_user

    # conversation thuộc teacher-test
    cid = client.post("/api/chat/conversations", json={}, headers=auth("teacher")).json()["id"]

    # teacher khác không xem được
    create_user("other@example.com", "Other", "teacher", hash_password("pw"))
    other = client.post(
        "/api/auth/login", json={"email": "other@example.com", "password": "pw"}
    ).json()["access_token"]
    r = client.get(
        f"/api/chat/conversations/{cid}", headers={"Authorization": f"Bearer {other}"}
    )
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"


def test_admin_can_access_any_conversation(
    client: TestClient, auth  # type: ignore[no-untyped-def]
) -> None:
    cid = client.post("/api/chat/conversations", json={}, headers=auth("teacher")).json()["id"]
    r = client.get(f"/api/chat/conversations/{cid}", headers=auth("admin"))
    assert r.status_code == 200


def test_missing_conversation_404(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.get(
        "/api/chat/conversations/00000000-0000-0000-0000-000000000000",
        headers=auth("teacher"),
    )
    assert r.status_code == 404
