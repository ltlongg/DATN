"""Unit test agent client: parse SSE + error mapping trước khi stream mở."""

from __future__ import annotations

import httpx
import pytest

import app.services.agent_client as ac
from app.core.errors import AppError
from app.services.agent_client import (
    AgentAskRequest,
    _parse_sse,
    format_sse,
    open_ask_stream,
)

async def _lines(text: str):  # type: ignore[no-untyped-def]
    for line in text.split("\n"):
        yield line

async def test_parse_sse_multiple_events() -> None:
    wire = (
        format_sse("token", {"text": "a"})
        + format_sse("token", {"text": "b"})
        + format_sse("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})
    )
    events = [(e.event, e.data) async for e in _parse_sse(_lines(wire))]
    assert [e[0] for e in events] == ["token", "token", "done"]
    assert events[0][1] == {"text": "a"}
    assert events[2][1]["confidence"] == "cao"

async def test_parse_sse_skips_comment_lines() -> None:
    wire = ": keep-alive\n\n" + format_sse("token", {"text": "x"})
    events = [e.event async for e in _parse_sse(_lines(wire))]
    assert events == ["token"]

def _patch_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:  # type: ignore[no-untyped-def]
    orig = ac.httpx.AsyncClient

    def factory(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["transport"] = httpx.MockTransport(handler)
        return orig(*args, **kwargs)

    monkeypatch.setattr(ac.httpx, "AsyncClient", factory)

async def test_open_stream_happy_path(monkeypatch: pytest.MonkeyPatch) -> None:
    body = format_sse("token", {"text": "hi"}) + format_sse(
        "done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []}
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body.encode("utf-8"))

    _patch_transport(monkeypatch, handler)
    stream = await open_ask_stream(AgentAskRequest(question="hi"))
    events = [e.event async for e in stream.events()]
    assert events == ["token", "done"]

async def test_open_stream_422_maps_to_502(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_transport(monkeypatch, lambda req: httpx.Response(422, json={"detail": "bad"}))
    with pytest.raises(AppError) as exc:
        await open_ask_stream(AgentAskRequest(question="hi"))
    assert exc.value.status_code == 502
    assert exc.value.code == "agent_bad_response"

async def test_open_stream_connect_error_maps_to_503(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    _patch_transport(monkeypatch, handler)
    with pytest.raises(AppError) as exc:
        await open_ask_stream(AgentAskRequest(question="hi"))
    assert exc.value.status_code == 503
    assert exc.value.code == "agent_unavailable"

async def test_open_stream_connect_timeout_maps_to_504(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    _patch_transport(monkeypatch, handler)
    with pytest.raises(AppError) as exc:
        await open_ask_stream(AgentAskRequest(question="hi"))
    assert exc.value.status_code == 504
    assert exc.value.code == "agent_timeout"
