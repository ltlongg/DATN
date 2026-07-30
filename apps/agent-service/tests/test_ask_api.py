"""Test /ask + /health + /ready qua FastAPI TestClient (retrieval/LLM/viz mock).

Phủ: happy path stream=False, validation 422, dependency 503, timeout 504, SSE stream=True,
health/ready, và auth nội bộ `X-Internal-Key` (thiếu/sai key -> 401).
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api import ask as ask_module
from app.api import health as health_module
from app.core.config import get_settings
from app.core.internal_auth import INTERNAL_KEY_HEADER
from app.main import app
from app.orchestrator import nodes
from app.schemas.ask import BuildQueryOutput, SynthesizedAnswer
from app.schemas.guardrails import GuardrailDecision
from app.schemas.retrieval import RetrievalBackendError, RetrievalResult, RetrievedChunk
from app.schemas.visualization import VisualizationPayload

# `/ask` gác X-Internal-Key -> client mặc định mang key thật (đọc root .env) để mọi test cũ
# chạy như trước; đường auth vẫn được đi qua thật chứ không bị dependency_override tắt.
client = TestClient(app, headers={INTERNAL_KEY_HEADER: get_settings().internal_api_key})


@pytest.fixture(autouse=True)
def _allow_guardrails(monkeypatch):
    """guard_input đứng đầu graph; mặc định allow để test /ask không gọi LLM guardrails thật
    (guard_input dùng client riêng trong module guardrails, không bị _patch_graph phủ)."""

    async def allow(question, history, **_kwargs):
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

    async def fake_retrieve(question, *, seed_mentions=None, **kwargs):
        if retrieve_error:
            raise retrieve_error
        return _retrieval(["c-1"])

    monkeypatch.setattr(nodes, "retrieve_hybrid", fake_retrieve)

    async def fake_synth(
        messages, *, emitter, model, batch_chars, temperature=0.0, client=None, on_usage=None
    ):
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
        health_module,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="k",
            database_url="d",
            qdrant_host="h",
            neo4j_uri="n",
            internal_api_key="key",
        ),
    )
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_ready_503_when_config_missing(monkeypatch) -> None:
    monkeypatch.setattr(
        health_module,
        "get_settings",
        lambda: SimpleNamespace(
            openai_api_key="",
            database_url="",
            qdrant_host="",
            neo4j_uri="",
            internal_api_key="",
        ),
    )
    resp = client.get("/ready")
    assert resp.status_code == 503
    assert resp.json()["detail"]["code"] == "not_ready"


def test_probes_public_no_internal_key_needed() -> None:
    """Probe KHÔNG gác key — backend `_ping_agent` gọi /ready mà không mang header."""
    bare = TestClient(app)
    assert bare.get("/health").status_code == 200
    assert bare.get("/ready").status_code in (200, 503)  # tuỳ .env, miễn KHÔNG phải 401


# --- auth nội bộ X-Internal-Key ---


def test_ask_401_without_internal_key() -> None:
    bare = TestClient(app)
    resp = bare.post("/ask", json={"question": "hỏi", "stream": False})
    assert resp.status_code == 401
    assert resp.json()["detail"]["code"] == "unauthenticated"


def test_ask_401_with_wrong_internal_key() -> None:
    wrong = TestClient(app, headers={INTERNAL_KEY_HEADER: "sai-key"})
    resp = wrong.post("/ask", json={"question": "hỏi", "stream": False})
    assert resp.status_code == 401


def test_ask_500_when_server_key_not_configured(monkeypatch) -> None:
    """Key rỗng ở server = chưa cấu hình -> 500 (fail-closed), KHÔNG phải bỏ qua check."""
    from app.core import internal_auth

    monkeypatch.setattr(
        internal_auth, "get_settings", lambda: SimpleNamespace(internal_api_key="")
    )
    resp = client.post("/ask", json={"question": "hỏi", "stream": False})
    assert resp.status_code == 500
    assert resp.json()["detail"]["code"] == "internal_key_not_configured"
