"""Gác debug server-side: chỉ admin được bật debug; user (user) bị ép debug=False.

Kiểm qua payload backend gửi sang agent (mock_agent.captured) — event `debug` chỉ do
agent phát khi request.debug=True, nên ép cờ ở backend là đủ.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.agent_client import format_sse

_DONE = format_sse("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})


def _new_conversation(client: TestClient, headers: dict[str, str]) -> str:
    return client.post("/api/chat/conversations", json={}, headers=headers).json()["id"]


def test_debug_forced_false_for_user(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    user = auth("user")
    cid = _new_conversation(client, user)
    mock_agent.configure(events=format_sse("token", {"text": "x"}) + _DONE)
    client.post(
        f"/api/chat/conversations/{cid}/ask",
        json={"question": "q", "debug": True},
        headers=user,
    )
    assert mock_agent.captured["payload"]["debug"] is False


def test_debug_honored_for_admin(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    admin = auth("admin")
    cid = _new_conversation(client, admin)
    mock_agent.configure(events=format_sse("token", {"text": "x"}) + _DONE)
    client.post(
        f"/api/chat/conversations/{cid}/ask",
        json={"question": "q", "debug": True},
        headers=admin,
    )
    assert mock_agent.captured["payload"]["debug"] is True
