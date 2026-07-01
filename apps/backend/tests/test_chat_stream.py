"""API test /ask streaming: proxy event, gom token lưu message, clarification, lỗi agent."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.services.agent_client import format_sse


def _parse_stream(text: str) -> list[tuple[str, dict]]:
    """Tách text SSE thành [(event, data), ...]."""
    events: list[tuple[str, dict]] = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        event = "message"
        data = "{}"
        for line in block.splitlines():
            if line.startswith("event:"):
                event = line[len("event:") :].strip()
            elif line.startswith("data:"):
                data = line[len("data:") :].strip()
        events.append((event, json.loads(data)))
    return events


def _new_conversation(client: TestClient, headers: dict[str, str]) -> str:
    return client.post("/api/chat/conversations", json={}, headers=headers).json()["id"]


def test_ask_streams_and_persists_answer(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    teacher = auth("teacher")
    cid = _new_conversation(client, teacher)
    mock_agent.configure(
        events=(
            format_sse("token", {"text": "Trương Định "})
            + format_sse("token", {"text": "chống Pháp."})
            + format_sse("citations", {"citations": [{"chunk_id": "c1"}]})
            + format_sse("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})
        )
    )
    r = client.post(
        f"/api/chat/conversations/{cid}/ask",
        json={"question": "Trương Định chống Pháp thế nào?"},
        headers=teacher,
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = _parse_stream(r.text)
    types = [e[0] for e in events]
    assert types == ["token", "token", "citations", "done"]
    done = events[-1][1]
    assert done["conversation_id"] == cid
    assert done["message_id"]  # đã lưu -> có id

    # message lưu DB khớp nội dung frontend thấy
    detail = client.get(f"/api/chat/conversations/{cid}", headers=teacher).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assistant = detail["messages"][1]
    assert assistant["content"] == "Trương Định chống Pháp."
    assert assistant["confidence"] == "cao"
    assert assistant["citations"] == [{"chunk_id": "c1"}]


def test_ask_sends_question_and_first_turn_history_empty(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    teacher = auth("teacher")
    cid = _new_conversation(client, teacher)
    mock_agent.configure(
        events=format_sse("token", {"text": "ok"})
        + format_sse("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})
    )
    client.post(
        f"/api/chat/conversations/{cid}/ask", json={"question": "Câu hỏi 1"}, headers=teacher
    )
    payload = mock_agent.captured["payload"]
    assert payload["question"] == "Câu hỏi 1"
    assert payload["history"] == []
    assert payload["stream"] is True


def test_ask_forwards_selected_mode(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    teacher = auth("teacher")
    cid = _new_conversation(client, teacher)
    mock_agent.configure(
        events=format_sse("token", {"text": "x"})
        + format_sse("done", {"confidence": "cao", "retrieval_mode": "graph", "warnings": []})
    )
    client.post(
        f"/api/chat/conversations/{cid}/ask",
        json={"question": "Q", "mode": "graph"},
        headers=teacher,
    )
    assert mock_agent.captured["payload"]["mode"] == "graph"


def test_ask_default_mode_is_hybrid(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    teacher = auth("teacher")
    cid = _new_conversation(client, teacher)
    mock_agent.configure(
        events=format_sse("token", {"text": "x"})
        + format_sse("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})
    )
    client.post(
        f"/api/chat/conversations/{cid}/ask", json={"question": "Q"}, headers=teacher
    )
    assert mock_agent.captured["payload"]["mode"] == "hybrid"


def test_ask_second_turn_includes_prior_history(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    teacher = auth("teacher")
    cid = _new_conversation(client, teacher)
    ok = format_sse("token", {"text": "trả lời"}) + format_sse(
        "done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []}
    )
    mock_agent.configure(events=ok)
    client.post(f"/api/chat/conversations/{cid}/ask", json={"question": "Q1"}, headers=teacher)
    mock_agent.configure(events=ok)
    client.post(f"/api/chat/conversations/{cid}/ask", json={"question": "Q2"}, headers=teacher)

    history = mock_agent.captured["payload"]["history"]
    assert [h["role"] for h in history] == ["user", "assistant"]
    assert history[0]["content"] == "Q1"


def test_ask_first_question_sets_title(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    teacher = auth("teacher")
    cid = _new_conversation(client, teacher)
    mock_agent.configure(
        events=format_sse("token", {"text": "x"})
        + format_sse("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})
    )
    client.post(
        f"/api/chat/conversations/{cid}/ask",
        json={"question": "Phong trào Cần Vương là gì?"},
        headers=teacher,
    )
    detail = client.get(f"/api/chat/conversations/{cid}", headers=teacher).json()
    assert detail["title"] == "Phong trào Cần Vương là gì?"


def test_ask_clarification_persisted(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    teacher = auth("teacher")
    cid = _new_conversation(client, teacher)
    mock_agent.configure(
        events=format_sse("clarification", {"question": "Bạn hỏi giai đoạn nào?"})
        + format_sse("done", {"confidence": None, "retrieval_mode": "none", "warnings": []})
    )
    r = client.post(
        f"/api/chat/conversations/{cid}/ask", json={"question": "kể chuyện"}, headers=teacher
    )
    events = _parse_stream(r.text)
    assert ("clarification", {"question": "Bạn hỏi giai đoạn nào?"}) in events

    detail = client.get(f"/api/chat/conversations/{cid}", headers=teacher).json()
    assistant = detail["messages"][1]
    assert assistant["clarification_needed"] is True
    assert assistant["content"] == "Bạn hỏi giai đoạn nào?"


def test_ask_error_event_not_persisted(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    teacher = auth("teacher")
    cid = _new_conversation(client, teacher)
    mock_agent.configure(
        events=format_sse("error", {"code": "qdrant_unavailable", "message": "x"})
    )
    r = client.post(
        f"/api/chat/conversations/{cid}/ask", json={"question": "q"}, headers=teacher
    )
    assert r.status_code == 200  # stream đã mở -> lỗi đi qua event
    events = _parse_stream(r.text)
    assert events[-1][0] == "error"
    # chỉ user message được lưu, không có assistant
    detail = client.get(f"/api/chat/conversations/{cid}", headers=teacher).json()
    assert [m["role"] for m in detail["messages"]] == ["user"]


def test_ask_agent_unavailable_returns_503(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    import httpx

    teacher = auth("teacher")
    cid = _new_conversation(client, teacher)
    mock_agent.configure(exc=httpx.ConnectError("refused"))
    r = client.post(
        f"/api/chat/conversations/{cid}/ask", json={"question": "q"}, headers=teacher
    )
    assert r.status_code == 503
    assert r.json()["code"] == "agent_unavailable"


def test_ask_blocked_for_non_owner(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    from app.core.security import hash_password
    from app.models.user import create_user

    cid = _new_conversation(client, auth("teacher"))
    create_user("intruder@example.com", "Intruder", "teacher", hash_password("pw"))
    token = client.post(
        "/api/auth/login", json={"email": "intruder@example.com", "password": "pw"}
    ).json()["access_token"]
    r = client.post(
        f"/api/chat/conversations/{cid}/ask",
        json={"question": "q"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "forbidden"
