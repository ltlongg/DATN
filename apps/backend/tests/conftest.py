"""Fixtures dùng chung cho test backend.

Isolation DB: dùng MỘT connection thật, vô hiệu `commit` (no-op) và `rollback` ở cuối
mỗi test -> mọi thay đổi bị huỷ, các test không dây vào nhau và không làm bẩn DB remote.
Repo import `connection` theo tên nên patch ở từng module model + core.db.

Mock agent-service: patch `httpx.AsyncClient` trong agent_client bằng MockTransport để
test streaming không cần agent thật.
"""

from __future__ import annotations

import importlib
from contextlib import contextmanager
from types import SimpleNamespace

import httpx
import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app.core import db
from app.core.security import hash_password
from app.main import app

# Module có `from app.core.db import connection` -> phải patch từng nơi.
_DB_MODULES = (
    "app.core.db",
    "app.models.user",
    "app.models.conversation",
    "app.models.document",
    "app.models.inspect",
    "app.models.timeline",
    "app.models.logs",
    "app.models.cost",
    "app.models.prompt",
    "app.models.activity",
    "app.models.config",
)

@pytest.fixture(scope="session", autouse=True)
def _ensure_schema() -> None:
    # CREATE TABLE IF NOT EXISTS — an toàn chạy lại; commit thật 1 lần ở session scope.
    with psycopg.connect(db._database_url()) as conn:
        db.init_schema(conn)

@pytest.fixture
def db_conn(monkeypatch: pytest.MonkeyPatch) -> psycopg.Connection:
    conn = psycopg.connect(db._database_url(), row_factory=dict_row)
    conn.commit = lambda: None  # type: ignore[method-assign]  # giữ mọi thay đổi trong 1 txn

    @contextmanager
    def fake_connection(database_url: str | None = None):  # type: ignore[no-untyped-def]
        yield conn

    for name in _DB_MODULES:
        monkeypatch.setattr(importlib.import_module(name), "connection", fake_connection)

    yield conn
    conn.rollback()
    conn.close()

@pytest.fixture
def client(db_conn: psycopg.Connection) -> TestClient:
    return TestClient(app)

@pytest.fixture
def users(db_conn: psycopg.Connection) -> dict[str, object]:
    from app.models.user import create_user

    # Email test riêng (không đụng seed thật); txn rollback nên không tích luỹ.
    admin = create_user("admin-test@example.com", "Admin Test", "admin", hash_password("adminpw"))
    user = create_user(
        "user-test@example.com", "User Test", "user", hash_password("userpw")
    )
    return {"admin": admin, "user": user}

@pytest.fixture
def auth(client: TestClient, users: dict[str, object]):  # type: ignore[no-untyped-def]
    """Trả header Authorization cho role 'admin' | 'user'."""
    creds = {
        "admin": ("admin-test@example.com", "adminpw"),
        "user": ("user-test@example.com", "userpw"),
    }

    def headers_for(role: str) -> dict[str, str]:
        email, pw = creds[role]
        resp = client.post("/api/auth/login", json={"email": email, "password": pw})
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return headers_for

@pytest.fixture
def mock_agent(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Patch agent-service HTTP. `configure(events=..., status=..., exc=...)` đặt phản hồi;
    `.captured['payload']` là body backend gửi sang agent."""
    import app.services.agent_client as ac

    state = {"events": "", "status": 200, "exc": None}
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        captured["payload"] = json.loads(request.content)
        if state["exc"] is not None:
            raise state["exc"]  # type: ignore[misc]
        return httpx.Response(
            int(state["status"]),
            content=str(state["events"]).encode("utf-8"),
            headers={"content-type": "text/event-stream"},
        )

    orig = ac.httpx.AsyncClient

    def factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["transport"] = httpx.MockTransport(handler)
        return orig(*args, **kwargs)

    monkeypatch.setattr(ac.httpx, "AsyncClient", factory)

    def configure(events: str = "", status: int = 200, exc: Exception | None = None) -> None:
        state.update(events=events, status=status, exc=exc)

    return SimpleNamespace(configure=configure, captured=captured)
