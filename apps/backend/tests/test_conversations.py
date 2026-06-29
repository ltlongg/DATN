"""API test conversation CRUD + unit test bounded history / derive_title."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.models.conversation import Message
from app.services.conversation_service import (
    DEFAULT_TITLE,
    build_bounded_history,
    derive_title,
)


def test_create_conversation_default_title(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.post("/api/chat/conversations", json={}, headers=auth("teacher"))
    assert r.status_code == 201
    assert r.json()["title"] == DEFAULT_TITLE


def test_create_conversation_with_title(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.post(
        "/api/chat/conversations", json={"title": "Trương Định"}, headers=auth("teacher")
    )
    assert r.status_code == 201
    assert r.json()["title"] == "Trương Định"


def test_list_only_own_conversations(client: TestClient, auth) -> None:  # type: ignore[no-untyped-def]
    teacher = auth("teacher")
    client.post("/api/chat/conversations", json={}, headers=teacher)
    client.post("/api/chat/conversations", json={}, headers=teacher)
    r = client.get("/api/chat/conversations", headers=teacher)
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_conversation_detail_includes_messages(
    client: TestClient, auth  # type: ignore[no-untyped-def]
) -> None:
    from app.models import conversation as cr

    cid = client.post("/api/chat/conversations", json={}, headers=auth("teacher")).json()["id"]
    cr.add_message(cid, "user", "Câu hỏi")
    cr.add_message(cid, "assistant", "Trả lời", confidence="cao", citations=[{"chunk_id": "c1"}])
    r = client.get(f"/api/chat/conversations/{cid}", headers=auth("teacher"))
    body = r.json()
    assert len(body["messages"]) == 2
    assert body["messages"][0]["role"] == "user"
    assert body["messages"][1]["citations"] == [{"chunk_id": "c1"}]


# --- unit: derive_title ---


def test_derive_title_short() -> None:
    assert derive_title("Trương Định là ai?") == "Trương Định là ai?"


def test_derive_title_truncates_long() -> None:
    title = derive_title("a " * 100)
    assert len(title) <= 81  # 80 + dấu …
    assert title.endswith("…")


def test_derive_title_collapses_newlines() -> None:
    assert derive_title("dòng 1\n\ndòng 2") == "dòng 1 dòng 2"


def test_derive_title_empty_falls_back() -> None:
    assert derive_title("   ") == DEFAULT_TITLE


# --- unit: build_bounded_history ---


def _msg(role: str, content: str) -> Message:
    return Message(
        id="x",
        conversation_id="c",
        role=role,
        content=content,
        created_at=datetime.now(tz=timezone.utc),
    )


def test_bounded_history_keeps_last_n() -> None:
    msgs = [_msg("user" if i % 2 == 0 else "assistant", f"m{i}") for i in range(20)]
    hist = build_bounded_history(msgs, 12)
    assert len(hist) == 12
    assert hist[-1]["content"] == "m19"
    assert hist[0]["content"] == "m8"


def test_bounded_history_drops_empty_assistant() -> None:
    msgs = [_msg("user", "hỏi"), _msg("assistant", "   "), _msg("user", "hỏi 2")]
    hist = build_bounded_history(msgs, 12)
    assert [h["content"] for h in hist] == ["hỏi", "hỏi 2"]


def test_bounded_history_keeps_clarification() -> None:
    msgs = [_msg("user", "hỏi mơ hồ"), _msg("assistant", "Bạn hỏi giai đoạn nào?")]
    hist = build_bounded_history(msgs, 12)
    assert len(hist) == 2
    assert hist[1]["content"] == "Bạn hỏi giai đoạn nào?"


def test_bounded_history_truncates_long_content() -> None:
    msgs = [_msg("user", "x" * 5000)]
    hist = build_bounded_history(msgs, 12)
    assert len(hist[0]["content"]) == 4000
