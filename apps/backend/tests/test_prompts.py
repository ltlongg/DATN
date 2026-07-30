"""Item 2 — quản lý Prompt: model (create_staging tăng version, promote đổi status trong
transaction) + endpoints (list/detail/version/promote + require_admin). Dùng key test riêng,
cô lập bằng txn rollback (conftest)."""

from __future__ import annotations

import uuid

import psycopg

from app.models import prompt as repo

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS managed_prompts (
        key TEXT PRIMARY KEY, grp TEXT NOT NULL, title TEXT NOT NULL,
        description TEXT, updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS prompt_versions (
        id UUID PRIMARY KEY, prompt_key TEXT NOT NULL REFERENCES managed_prompts(key),
        version_no INTEGER NOT NULL, content TEXT NOT NULL, note TEXT, status TEXT NOT NULL,
        created_by TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        promoted_by TEXT, promoted_at TIMESTAMPTZ, UNIQUE(prompt_key, version_no)
    );
    """,
)


def _seed_prompt(conn: psycopg.Connection, key: str) -> None:  # type: ignore[type-arg]
    with conn.cursor() as cur:
        for sql in _DDL:
            cur.execute(sql)
        cur.execute(
            "INSERT INTO managed_prompts (key, grp, title, description) "
            "VALUES (%s, 'ONLINE', 'Test', 'd')",
            (key,),
        )
        cur.execute(
            "INSERT INTO prompt_versions (id, prompt_key, version_no, content, note, status, "
            "created_by) VALUES (%s, %s, 1, 'V1 CONTENT', 'seed', 'production', 'system')",
            (str(uuid.uuid4()), key),
        )


# --- model ------------------------------------------------------------------


def test_create_staging_increments_version_no(db_conn) -> None:  # type: ignore[no-untyped-def]
    key = f"test-{uuid.uuid4().hex[:8]}"
    _seed_prompt(db_conn, key)
    v = repo.create_staging_version(key, "V2 CONTENT", "why", "admin@example.com")
    assert v is not None
    assert v["version_no"] == 2
    assert v["status"] == "staging"
    assert v["created_by"] == "admin@example.com"


def test_promote_switches_production_in_transaction(db_conn) -> None:  # type: ignore[no-untyped-def]
    key = f"test-{uuid.uuid4().hex[:8]}"
    _seed_prompt(db_conn, key)
    repo.create_staging_version(key, "V2", "note", "admin@example.com")  # version 2 = staging

    assert repo.promote(key, 2, "admin@example.com") is True
    detail = repo.get_prompt(key)
    assert detail is not None
    by_no = {v["version_no"]: v for v in detail["versions"]}
    assert by_no[2]["status"] == "production"
    assert by_no[2]["promoted_by"] == "admin@example.com"
    assert by_no[2]["promoted_at"] is not None
    assert by_no[1]["status"] == "archived"  # production cũ bị demote
    assert detail["production_content"] == "V2"  # content production đổi


def test_promote_unknown_version_returns_false(db_conn) -> None:  # type: ignore[no-untyped-def]
    key = f"test-{uuid.uuid4().hex[:8]}"
    _seed_prompt(db_conn, key)
    assert repo.promote(key, 99, "admin@example.com") is False


def test_get_version_content(db_conn) -> None:  # type: ignore[no-untyped-def]
    key = f"test-{uuid.uuid4().hex[:8]}"
    _seed_prompt(db_conn, key)
    v = repo.get_version(key, 1)
    assert v is not None and v["content"] == "V1 CONTENT" and v["status"] == "production"
    assert repo.get_version(key, 42) is None


# --- endpoints --------------------------------------------------------------


def test_list_and_detail_endpoints(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    key = f"test-{uuid.uuid4().hex[:8]}"
    _seed_prompt(db_conn, key)
    admin = auth("admin")

    listing = client.get("/api/admin/prompts", headers=admin)
    assert listing.status_code == 200
    item = next(p for p in listing.json() if p["key"] == key)
    assert item["active_version_no"] == 1 and item["version_count"] == 1

    detail = client.get(f"/api/admin/prompts/{key}", headers=admin)
    assert detail.status_code == 200
    body = detail.json()
    assert body["production_content"] == "V1 CONTENT"
    assert len(body["versions"]) == 1


def test_create_then_promote_endpoint_flow(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    key = f"test-{uuid.uuid4().hex[:8]}"
    _seed_prompt(db_conn, key)
    admin = auth("admin")

    created = client.post(
        f"/api/admin/prompts/{key}/versions",
        json={"content": "V2 CONTENT", "note": "cải tiến"},
        headers=admin,
    )
    assert created.status_code == 200
    assert created.json()["version_no"] == 2

    promoted = client.post(f"/api/admin/prompts/{key}/versions/2/promote", headers=admin)
    assert promoted.status_code == 200
    assert promoted.json()["production_content"] == "V2 CONTENT"


def test_prompts_require_admin(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    r = client.get("/api/admin/prompts", headers=auth("user"))
    assert r.status_code == 403


def test_detail_404_for_unknown_key(client, auth, db_conn) -> None:  # type: ignore[no-untyped-def]
    # Bảng tồn tại (seed thật) nhưng key này không có -> 404 (không phải 500).
    r = client.get(f"/api/admin/prompts/nope-{uuid.uuid4().hex[:6]}", headers=auth("admin"))
    assert r.status_code == 404
