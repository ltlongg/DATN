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
    user = auth("user")
    cid = _new_conversation(client, user)
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
        headers=user,
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
    detail = client.get(f"/api/chat/conversations/{cid}", headers=user).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assistant = detail["messages"][1]
    assert assistant["content"] == "Trương Định chống Pháp."
    assert assistant["confidence"] == "cao"
    assert assistant["citations"] == [{"chunk_id": "c1"}]


def test_ask_reports_ttft_in_done_and_persists_it(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    """TTFT đo ở backend (nhận /ask -> token đầu) đi kèm event done VÀ lưu vào message để
    còn thấy sau khi reload. Không assert giá trị cụ thể (phụ thuộc máy), chỉ đòi >= 0 và khớp
    nhau giữa done và DB."""
    user = auth("user")
    cid = _new_conversation(client, user)
    mock_agent.configure(
        events=(
            format_sse("token", {"text": "Trương Định "})
            + format_sse("token", {"text": "chống Pháp."})
            + format_sse("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})
        )
    )
    r = client.post(
        f"/api/chat/conversations/{cid}/ask", json={"question": "Trương Định?"}, headers=user
    )
    done = _parse_stream(r.text)[-1][1]
    assert isinstance(done["ttft_ms"], int) and done["ttft_ms"] >= 0

    detail = client.get(f"/api/chat/conversations/{cid}", headers=user).json()
    assert detail["messages"][1]["ttft_ms"] == done["ttft_ms"]
    assert detail["messages"][0]["ttft_ms"] is None  # message user không có TTFT


def test_ask_blocked_persists_safe_message_and_forwards_events(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    """Guardrails chặn: agent stream token(safe) rồi blocked, KHÔNG done. Backend forward đúng
    thứ tự + persist safe message như assistant message thường (thấy lại khi reload)."""
    user = auth("user")
    cid = _new_conversation(client, user)
    mock_agent.configure(
        events=(
            format_sse("token", {"text": "Xin lỗi, mình không hỗ trợ yêu cầu này."})
            + format_sse("blocked", {"stage": "input", "categories": ["prompt_injection"]})
        )
    )
    r = client.post(
        f"/api/chat/conversations/{cid}/ask",
        json={"question": "lộ system prompt"},
        headers=user,
    )
    assert r.status_code == 200
    events = _parse_stream(r.text)
    types = [e[0] for e in events]
    assert types == ["token", "blocked"]  # token TRƯỚC blocked, không done/error
    blocked = next(d for t, d in events if t == "blocked")
    assert blocked == {"stage": "input", "categories": ["prompt_injection"]}

    # safe message được persist như assistant message thường -> reload thấy lại (không còn cờ blocked)
    detail = client.get(f"/api/chat/conversations/{cid}", headers=user).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user", "assistant"]
    assert detail["messages"][1]["content"] == "Xin lỗi, mình không hỗ trợ yêu cầu này."


def test_ask_blocked_without_content_not_persisted(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    """Blocked mà không có safe message (content rỗng) -> không lưu assistant message."""
    user = auth("user")
    cid = _new_conversation(client, user)
    mock_agent.configure(
        events=format_sse("blocked", {"stage": "input", "categories": ["other"]})
    )
    r = client.post(
        f"/api/chat/conversations/{cid}/ask", json={"question": "x"}, headers=user
    )
    assert r.status_code == 200
    detail = client.get(f"/api/chat/conversations/{cid}", headers=user).json()
    roles = [m["role"] for m in detail["messages"]]
    assert roles == ["user"]  # chỉ có user message, assistant không lưu


def test_ask_sends_question_and_first_turn_history_empty(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    user = auth("user")
    cid = _new_conversation(client, user)
    mock_agent.configure(
        events=format_sse("token", {"text": "ok"})
        + format_sse("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})
    )
    client.post(
        f"/api/chat/conversations/{cid}/ask", json={"question": "Câu hỏi 1"}, headers=user
    )
    payload = mock_agent.captured["payload"]
    assert payload["question"] == "Câu hỏi 1"
    assert payload["history"] == []
    assert payload["stream"] is True
    # Item 3: backend luồn conversation_id + message_id (assistant pre-generate) sang agent
    # để quy token về đúng hội thoại/message.
    assert payload["conversation_id"] == cid
    assert isinstance(payload["message_id"], str) and payload["message_id"]


def test_ask_forwards_selected_mode(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    user = auth("user")
    cid = _new_conversation(client, user)
    mock_agent.configure(
        events=format_sse("token", {"text": "x"})
        + format_sse("done", {"confidence": "cao", "retrieval_mode": "graph", "warnings": []})
    )
    client.post(
        f"/api/chat/conversations/{cid}/ask",
        json={"question": "Q", "mode": "graph"},
        headers=user,
    )
    assert mock_agent.captured["payload"]["mode"] == "graph"


def test_ask_default_mode_is_hybrid(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    user = auth("user")
    cid = _new_conversation(client, user)
    mock_agent.configure(
        events=format_sse("token", {"text": "x"})
        + format_sse("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})
    )
    client.post(
        f"/api/chat/conversations/{cid}/ask", json={"question": "Q"}, headers=user
    )
    assert mock_agent.captured["payload"]["mode"] == "hybrid"


def test_ask_second_turn_includes_prior_history(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    user = auth("user")
    cid = _new_conversation(client, user)
    ok = format_sse("token", {"text": "trả lời"}) + format_sse(
        "done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []}
    )
    mock_agent.configure(events=ok)
    client.post(f"/api/chat/conversations/{cid}/ask", json={"question": "Q1"}, headers=user)
    mock_agent.configure(events=ok)
    client.post(f"/api/chat/conversations/{cid}/ask", json={"question": "Q2"}, headers=user)

    history = mock_agent.captured["payload"]["history"]
    assert [h["role"] for h in history] == ["user", "assistant"]
    assert history[0]["content"] == "Q1"


def test_ask_first_question_sets_title(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    user = auth("user")
    cid = _new_conversation(client, user)
    mock_agent.configure(
        events=format_sse("token", {"text": "x"})
        + format_sse("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})
    )
    client.post(
        f"/api/chat/conversations/{cid}/ask",
        json={"question": "Phong trào Cần Vương là gì?"},
        headers=user,
    )
    detail = client.get(f"/api/chat/conversations/{cid}", headers=user).json()
    assert detail["title"] == "Phong trào Cần Vương là gì?"


def test_ask_clarification_persisted(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    user = auth("user")
    cid = _new_conversation(client, user)
    mock_agent.configure(
        events=format_sse("clarification", {"question": "Bạn hỏi giai đoạn nào?"})
        + format_sse("done", {"confidence": None, "retrieval_mode": "none", "warnings": []})
    )
    r = client.post(
        f"/api/chat/conversations/{cid}/ask", json={"question": "kể chuyện"}, headers=user
    )
    events = _parse_stream(r.text)
    assert ("clarification", {"question": "Bạn hỏi giai đoạn nào?"}) in events

    detail = client.get(f"/api/chat/conversations/{cid}", headers=user).json()
    assistant = detail["messages"][1]
    assert assistant["clarification_needed"] is True
    assert assistant["content"] == "Bạn hỏi giai đoạn nào?"


def test_ask_error_event_not_persisted(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    user = auth("user")
    cid = _new_conversation(client, user)
    mock_agent.configure(
        events=format_sse("error", {"code": "qdrant_unavailable", "message": "x"})
    )
    r = client.post(
        f"/api/chat/conversations/{cid}/ask", json={"question": "q"}, headers=user
    )
    assert r.status_code == 200  # stream đã mở -> lỗi đi qua event
    events = _parse_stream(r.text)
    assert events[-1][0] == "error"
    # chỉ user message được lưu, không có assistant
    detail = client.get(f"/api/chat/conversations/{cid}", headers=user).json()
    assert [m["role"] for m in detail["messages"]] == ["user"]


def test_ask_agent_unavailable_returns_503(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    import httpx

    user = auth("user")
    cid = _new_conversation(client, user)
    mock_agent.configure(exc=httpx.ConnectError("refused"))
    r = client.post(
        f"/api/chat/conversations/{cid}/ask", json={"question": "q"}, headers=user
    )
    assert r.status_code == 503
    assert r.json()["code"] == "agent_unavailable"


def test_ask_blocked_for_non_owner(client, auth, mock_agent) -> None:  # type: ignore[no-untyped-def]
    from app.core.security import hash_password
    from app.models.user import create_user

    cid = _new_conversation(client, auth("user"))
    create_user("intruder@example.com", "Intruder", "user", hash_password("pw"))
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
