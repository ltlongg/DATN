"""API test admin documents mock CRUD."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_admin_document_crud(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    admin = auth("admin")

    # create
    r = client.post(
        "/api/admin/documents",
        json={"name": "lichsu.clean.md", "type": "markdown", "status": "indexed", "chunk_count": 1213},
        headers=admin,
    )
    assert r.status_code == 201
    doc = r.json()
    assert doc["name"] == "lichsu.clean.md"
    assert doc["chunk_count"] == 1213
    did = doc["id"]

    # list
    r = client.get("/api/admin/documents", headers=admin)
    assert r.status_code == 200
    assert any(d["id"] == did for d in r.json())

    # patch (partial — chỉ status đổi, name giữ nguyên)
    r = client.patch(f"/api/admin/documents/{did}", json={"status": "failed"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["status"] == "failed"
    assert r.json()["name"] == "lichsu.clean.md"

    # delete
    assert client.delete(f"/api/admin/documents/{did}", headers=admin).status_code == 200
    assert client.delete(f"/api/admin/documents/{did}", headers=admin).status_code == 404


def test_create_document_defaults(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/admin/documents", json={"name": "doc.md"}, headers=auth("admin"))
    assert r.status_code == 201
    assert r.json()["status"] == "draft"
    assert r.json()["type"] == "markdown"
    assert r.json()["chunk_count"] == 0


def test_invalid_status_rejected(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.post(
        "/api/admin/documents", json={"name": "doc.md", "status": "bogus"}, headers=auth("admin")
    )
    assert r.status_code == 422


def test_patch_missing_document_404(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.patch(
        "/api/admin/documents/00000000-0000-0000-0000-000000000000",
        json={"status": "draft"},
        headers=auth("admin"),
    )
    assert r.status_code == 404
