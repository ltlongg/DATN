"""Test /ask + /health + /ready qua FastAPI TestClient (retrieval/LLM/viz mock).

Phủ: happy path stream=False, validation 422, dependency 503, timeout 504, SSE stream=True,
health/ready.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import ask as ask_module
from app.main import app
from app.orchestrator import nodes
from app.schemas.ask import BuildQueryOutput, SynthesizedAnswer
from app.schemas.guardrails import GuardrailDecision
from app.schemas.retrieval import RetrievalBackendError, RetrievalResult, RetrievedChunk
from app.schemas.visualization import VisualizationPayload

client = TestClient(app)


@pytest.fixture(autouse=True)
def _allow_guardrails(monkeypatch):
    """guard_input đứng đầu graph; mặc định allow để test /ask không gọi LLM guardrails thật
    (guard_input dùng client riêng trong module guardrails, không bị _patch_graph phủ)."""

    async def allow(question, history, *, user_id=None):
        return GuardrailDecision(action="allow")

    monkeypatch.setattr(nodes, "check_input", allow)


def _retrieval(chunk_ids) -> RetrievalResult:
    return RetrievalResult(
        mode="hybrid",
        query="q",
        chunks=[
            RetrievedChunk(chunk_id=c, text=f"t {c}", metadata={}, heading_path=[])
            for c in chunk_ids
        ],
    )


def _patch_graph(monkeypatch, *, route="needs_retrieval", retrieve_error=None):
    output = BuildQueryOutput(standalone_query="q", mentioned_entities=[], route=route)

    async def fake_parse(**kw):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=output))])

    monkeypatch.setattr(
        nodes,
        "get_async_openai_client",
        lambda: SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(parse=fake_parse))
        ),
    )

    async def fake_retrieve(question, *, seed_mentions=None):
        if retrieve_error:
            raise retrieve_error
        return _retrieval(["c-1"])

    monkeypatch.setattr(nodes, "retrieve_hybrid", fake_retrieve)

    async def fake_synth(messages, *, emitter, model, batch_chars, client=None, on_usage=None):
        from app.orchestrator.synthesis import emit_text_as_batches

        await emit_text_as_batches("Đáp án.", emitter, batch_chars)
        return SynthesizedAnswer(answer="Đáp án.", used_chunk_ids=["c-1"], confidence="cao")

    monkeypatch.setattr(nodes, "stream_synthesis", fake_synth)
    monkeypatch.setattr(nodes, "build_visualization_payload", lambda ids: VisualizationPayload())


# --- /ask stream=False ---


def test_ask_happy_path_stream_false(monkeypatch) -> None:
    _patch_graph(monkeypatch)
    resp = client.post("/ask", json={"question": "Trương Định là ai?", "stream": False})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"] == "Đáp án."
    assert body["retrieval_mode"] == "hybrid"
    assert body["citations"][0]["chunk_id"] == "c-1"


def test_ask_empty_question_422() -> None:
    resp = client.post("/ask", json={"question": "", "stream": False})
    assert resp.status_code == 422


def test_ask_history_too_large_422() -> None:
    history = [{"role": "user", "content": "x"} for _ in range(13)]
    resp = client.post("/ask", json={"question": "hỏi", "history": history, "stream": False})
    assert resp.status_code == 422


def test_ask_dependency_error_503(monkeypatch) -> None:
    _patch_graph(monkeypatch, retrieve_error=RetrievalBackendError("all_backends_failed"))
    resp = client.post("/ask", json={"question": "hỏi", "stream": False})
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "all_backends_failed"


def test_ask_timeout_504(monkeypatch) -> None:
    async def slow(request, **kw):
        await asyncio.sleep(0.2)

    monkeypatch.setattr(ask_module, "run_ask", slow)
    monkeypatch.setattr(ask_module, "get_settings", lambda: SimpleNamespace(ask_timeout_seconds=0.01))
    resp = client.post("/ask", json={"question": "hỏi", "stream": False})
    assert resp.status_code == 504
    assert resp.json()["detail"]["code"] == "timeout"


# --- /ask stream=True (SSE) ---


def test_ask_stream_true_returns_sse(monkeypatch) -> None:
    _patch_graph(monkeypatch)
    resp = client.post("/ask", json={"question": "hỏi", "stream": True})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert "event: done" in resp.text
    assert "event: token" in resp.text
    assert "event: citations" in resp.text


# --- /health + /ready ---


def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_ready_ok_when_config_present(monkeypatch) -> None:
    monkeypatch.setattr(
        ask_module,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="k", database_url="d", qdrant_host="h", neo4j_uri="n"
        ),
    )
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_ready_503_when_config_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        ask_module,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="", database_url="", qdrant_host="", neo4j_uri=""
        ),
    )
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "not_ready"
