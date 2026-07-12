"""Test run_ask_stream (SSE): thứ tự event, token chỉ trong synthesize, clarify không
token, lỗi sau khi mở SSE đi qua event error.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.orchestrator import nodes
from app.orchestrator.runner import run_ask_stream
from app.schemas.ask import AskRequest, BuildQueryOutput, SynthesizedAnswer
from app.schemas.guardrails import GuardrailDecision
from app.schemas.retrieval import RetrievalBackendError, RetrievalResult, RetrievedChunk
from app.schemas.visualization import VisualizationPayload


@pytest.fixture(autouse=True)
def _allow_guardrails(monkeypatch):
    """Mặc định guardrails allow để test luồng SSE hiện có (test block ở test_guardrails.py)."""

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


def _patch_build_query(monkeypatch, *, route="needs_retrieval"):
    output = BuildQueryOutput(standalone_query="q", mentioned_entities=[], route=route)

    async def fake_parse(**kw):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=output))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=fake_parse)))
    monkeypatch.setattr(nodes, "get_async_openai_client", lambda: client)


def _patch_retrieve(monkeypatch, result=None, *, error=None):
    async def fake(question, *, seed_mentions=None, **kwargs):
        if error:
            raise error
        return result if result is not None else _retrieval(["c-1"])

    monkeypatch.setattr(nodes, "retrieve_hybrid", fake)


def _patch_synthesize(monkeypatch, *, answer="Đáp án ngắn.", used=("c-1",), confidence="cao"):
    async def fake(
        messages, *, emitter, model, batch_chars, temperature=0.0, client=None, on_usage=None
    ):
        from app.orchestrator.synthesis import emit_text_as_batches

        await emit_text_as_batches(answer, emitter, batch_chars)
        return SynthesizedAnswer(answer=answer, used_chunk_ids=list(used), confidence=confidence)

    monkeypatch.setattr(nodes, "stream_synthesis", fake)


def _patch_viz(monkeypatch):
    monkeypatch.setattr(nodes, "build_visualization_payload", lambda ids: VisualizationPayload())


def _parse(chunk: str) -> tuple[str, dict]:
    lines = chunk.strip().split("\n")
    etype = lines[0].removeprefix("event: ")
    data = json.loads(lines[1].removeprefix("data: "))
    return etype, data


async def _collect(request: AskRequest) -> list[tuple[str, dict]]:
    return [_parse(c) async for c in run_ask_stream(request)]


# --- tests ---


async def test_happy_path_event_order(monkeypatch) -> None:
    _patch_build_query(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    types = [t for t, _ in events]
    assert types[0] == "status"
    assert types[-1] == "done"
    assert types.index("token") < types.index("citations") < types.index("visualization") < types.index("done")


async def test_token_concatenates_to_answer(monkeypatch) -> None:
    _patch_build_query(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, answer="Câu một. Câu hai.")
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    tokens = [d["text"] for t, d in events if t == "token"]
    assert "".join(tokens) == "Câu một. Câu hai."


async def test_done_summary_carries_confidence_and_mode(monkeypatch) -> None:
    _patch_build_query(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, confidence="vừa")
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    done = next(d for t, d in events if t == "done")
    assert done["confidence"] == "vừa"
    assert done["retrieval_mode"] == "hybrid"


async def test_clarify_emits_clarification_and_done_no_token(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="ambiguous")
    events = await _collect(AskRequest(question="Ông ấy là ai?", stream=True))
    types = [t for t, _ in events]
    assert "clarification" in types
    assert types[-1] == "done"
    assert "token" not in types
    clar = next(d for t, d in events if t == "clarification")
    assert clar["question"]


async def test_error_after_sse_open_goes_through_error_event(monkeypatch) -> None:
    _patch_build_query(monkeypatch)
    _patch_retrieve(monkeypatch, error=RetrievalBackendError("all_backends_failed"))
    events = await _collect(AskRequest(question="hỏi", stream=True))
    types = [t for t, _ in events]
    assert "status" in types  # SSE đã mở trước khi lỗi
    assert types[-1] == "error"
    assert "done" not in types
    err = next(d for t, d in events if t == "error")
    assert err["code"] == "all_backends_failed"
    assert "Traceback" not in err["message"]  # không dump stack


async def test_debug_event_emitted_before_done_when_requested(monkeypatch) -> None:
    _patch_build_query(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True, debug=True))
    types = [t for t, _ in events]
    assert types[-1] == "done"
    assert types[-2] == "debug"  # debug ngay trước done (gom rồi bắn 1 lần ở cuối)
    dbg = next(d for t, d in events if t == "debug")["debug"]
    # state["debug"] đã tích lũy build_query + retrieve qua reducer _merge_debug.
    assert "build_query" in dbg and "retrieve" in dbg


async def test_debug_event_absent_when_not_requested(monkeypatch) -> None:
    _patch_build_query(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True, debug=False))
    assert "debug" not in [t for t, _ in events]


async def test_smalltalk_streams_token_and_done(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="smalltalk")
    events = await _collect(AskRequest(question="Xin chào", stream=True))
    types = [t for t, _ in events]
    assert "token" in types
    assert types[-1] == "done"
    tokens = "".join(d["text"] for t, d in events if t == "token")
    assert "Xin chào" in tokens
