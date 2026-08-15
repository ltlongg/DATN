"""API test admin documents — danh mục tài liệu nối kho tri thức thật qua `source_file`."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

def _sources(client: TestClient, admin: dict[str, str]) -> list[dict]:
    r = client.get("/api/admin/documents/sources", headers=admin)
    assert r.status_code == 200
    return r.json()

def test_admin_document_crud(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    admin = auth("admin")

    # create — chưa gắn nguồn nào -> draft, kho rỗng.
    r = client.post(
        "/api/admin/documents",
        json={"name": "Tài liệu nháp", "type": "markdown"},
        headers=admin,
    )
    assert r.status_code == 201
    doc = r.json()
    assert doc["status"] == "draft"
    assert doc["source_file"] is None
    assert doc["chunk_count"] == 0 and doc["event_count"] == 0
    did = doc["id"]

    # list
    r = client.get("/api/admin/documents", headers=admin)
    assert r.status_code == 200
    assert any(d["id"] == did for d in r.json())

    # patch (partial — chỉ name đổi, status giữ nguyên)
    r = client.patch(f"/api/admin/documents/{did}", json={"name": "Đổi tên"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["name"] == "Đổi tên"
    assert r.json()["status"] == "draft"

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

def test_source_file_immutable_qua_patch(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    """`source_file` là khóa nối -> PATCH gửi lên bị bỏ qua, không đổi được nguồn."""
    admin = auth("admin")
    did = client.post("/api/admin/documents", json={"name": "d.md"}, headers=admin).json()["id"]

    r = client.patch(f"/api/admin/documents/{did}", json={"source_file": "hack.md"}, headers=admin)
    assert r.status_code == 200
    assert r.json()["source_file"] is None

def test_documents_requires_admin(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    user = auth("user")
    assert client.get("/api/admin/documents", headers=user).status_code == 403
    assert client.get("/api/admin/documents/sources", headers=user).status_code == 403

# --- nối kho thật (cần rag_chunks đã index; DB trống -> skip) ---

def test_nguon_trong_kho_tu_hien_o_danh_muc(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    """Chunk vào kho bằng script offline, không qua UI -> danh mục TỰ đồng bộ: mỗi nguồn
    thật thành 1 tài liệu, status 'indexed', số chunk/sự kiện là số ĐẾM THẬT."""
    admin = auth("admin")
    sources = _sources(client, admin)
    if not sources:
        pytest.skip("Kho rag_chunks trống — chưa index dataset.")

    docs = client.get("/api/admin/documents", headers=admin).json()
    by_source = {d["source_file"]: d for d in docs if d["source_file"]}

    for src in sources:
        doc = by_source[src["source_file"]]
        assert doc["status"] == "indexed"
        assert doc["chunk_count"] == src["chunk_count"] > 0
        assert doc["event_count"] == src["event_count"]

    # Idempotent: load lại không đẻ thêm bản ghi trùng.
    docs2 = client.get("/api/admin/documents", headers=admin).json()
    assert len(docs2) == len(docs)

def test_khong_xoa_duoc_tai_lieu_con_chunk_trong_kho(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    """Xoá khỏi danh mục trong khi chunk còn trong kho là vô nghĩa (sync dựng lại ngay)
    -> backend chặn 409. Xoá thật thuộc Bước 1 (gỡ khỏi kho)."""
    admin = auth("admin")
    if not _sources(client, admin):
        pytest.skip("Kho rag_chunks trống — chưa index dataset.")

    docs = client.get("/api/admin/documents", headers=admin).json()
    indexed = next(d for d in docs if d["source_file"])

    r = client.delete(f"/api/admin/documents/{indexed['id']}", headers=admin)
    assert r.status_code == 409
    assert r.json()["code"] == "document_indexed"
