"""Test answer flow qua run_ask với retrieval/LLM/visualization đã mock.

Phủ mọi nhánh: route (needs_retrieval/ambiguous/out_of_scope/smalltalk), has_context
(empty -> honest), synthesize (valid/invalid citation/insufficient/retry guard), citation
trust boundary, seed_mentions handoff, visualization (ok/error), build_query fallback.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.orchestrator import nodes
from app.orchestrator.emitter import ListEmitter
from app.orchestrator.runner import run_ask
from app.schemas.ask import AskRequest, BuildQueryOutput, SynthesizedAnswer
from app.schemas.retrieval import RetrievalBackendError, RetrievalResult, RetrievedChunk
from app.schemas.visualization import TimelineItem, VisualizationPayload


# --- helpers ---


def _chunk(chunk_id: str, **meta) -> RetrievedChunk:
    base = {
        "source_file": "lichsu.clean.md",
        "chunk_index": 42,
        "start_line": 100,
        "end_line": 120,
    }
    base.update(meta)
    return RetrievedChunk(
        chunk_id=chunk_id, text=f"text {chunk_id}", metadata=base, heading_path=["II", "2.1"]
    )


def _retrieval(chunk_ids, *, warnings=None, graph_context=None) -> RetrievalResult:
    return RetrievalResult(
        mode="hybrid",
        query="q",
        chunks=[_chunk(c) for c in chunk_ids],
        graph_context=graph_context or [],
        warnings=warnings or [],
    )


def _patch_build_query(monkeypatch, *, route="needs_retrieval", entities=None, error=False):
    output = BuildQueryOutput(
        standalone_query="standalone q", mentioned_entities=entities or [], route=route
    )

    async def fake_parse(**kw):
        if error:
            raise RuntimeError("llm down")
        msg = SimpleNamespace(parsed=output)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(parse=fake_parse))
    )
    monkeypatch.setattr(nodes, "get_async_openai_client", lambda: client)


def _patch_retrieve(monkeypatch, result=None, *, error=None, capture=None):
    async def fake(question, *, seed_mentions=None):
        if capture is not None:
            capture["question"] = question
            capture["seed_mentions"] = seed_mentions
        if error:
            raise error
        return result if result is not None else _retrieval(["c-1"])

    monkeypatch.setattr(nodes, "retrieve_hybrid", fake)


def _patch_synthesize(monkeypatch, *, answer="Đáp án.", used=("c-1",), confidence="cao", capture=None):
    async def fake(messages, *, emitter, model, batch_chars, client=None, on_usage=None):
        if capture is not None:
            capture.setdefault("calls", []).append(messages)
        # stream vài token cho giống thật
        await emitter.emit("token", {"text": answer})
        return SynthesizedAnswer(
            answer=answer, used_chunk_ids=list(used), confidence=confidence
        )

    monkeypatch.setattr(nodes, "stream_synthesis", fake)


def _patch_viz(monkeypatch, payload=None, *, error=False):
    def fake(used_ids):
        if error:
            raise RuntimeError("viz down")
        return payload if payload is not None else VisualizationPayload()

    monkeypatch.setattr(nodes, "build_visualization_payload", fake)


# --- route branches ---


async def test_needs_retrieval_happy_path(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1", "c-2"]))
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="Trương Định là ai?", stream=False))
    assert resp.answer == "Đáp án."
    assert resp.retrieval_mode == "hybrid"
    assert resp.confidence == "cao"
    assert [c.chunk_id for c in resp.citations] == ["c-1"]
    assert resp.clarification_needed is False


async def test_ambiguous_routes_to_clarify_without_retrieve(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="ambiguous")

    async def boom(*a, **k):  # retrieve KHÔNG được gọi
        raise AssertionError("không được retrieve khi ambiguous")

    monkeypatch.setattr(nodes, "retrieve_hybrid", boom)
    resp = await run_ask(AskRequest(question="Ông ấy làm gì sau đó?", stream=False))
    assert resp.clarification_needed is True
    assert resp.clarification_question
    assert resp.answer is None
    assert resp.citations == []
    assert resp.retrieval_mode == "none"


async def test_out_of_scope_routes_to_honest(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="out_of_scope")
    resp = await run_ask(AskRequest(question="2 + 2 bằng mấy?", stream=False))
    assert resp.retrieval_mode == "none"
    assert resp.confidence == "không đủ dữ liệu"
    assert "chưa tìm thấy đủ thông tin" in (resp.answer or "")


async def test_smalltalk_routes_to_direct_response(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="smalltalk")
    resp = await run_ask(AskRequest(question="Xin chào", stream=False))
    assert resp.retrieval_mode == "none"
    assert "Xin chào" in (resp.answer or "")
    assert "chưa tìm thấy đủ thông tin" not in (resp.answer or "")  # KHÔNG dùng honest message


# --- has_context ---


async def test_empty_retrieval_goes_honest(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval([]))

    async def boom(*a, **k):
        raise AssertionError("synthesize không được gọi khi không có chunk")

    monkeypatch.setattr(nodes, "stream_synthesis", boom)
    resp = await run_ask(AskRequest(question="hỏi gì đó", stream=False))
    assert resp.citations == []
    assert "chưa tìm thấy đủ thông tin" in (resp.answer or "")


# --- dependency error ---


async def test_retrieval_all_backends_fail_propagates(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, error=RetrievalBackendError("all_backends_failed"))
    with pytest.raises(RetrievalBackendError) as exc:
        await run_ask(AskRequest(question="hỏi", stream=False))
    assert exc.value.code == "all_backends_failed"


# --- citation trust boundary ---


async def test_invalid_citation_filtered_then_retry_then_honest(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    capture: dict = {}
    # LLM khai chunk_id không có trong retrieval -> bị drop -> citations rỗng -> retry -> honest.
    _patch_synthesize(monkeypatch, used=("ghost-id",), capture=capture)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert len(capture["calls"]) == 2  # đúng 1 retry rồi dừng (synthesize_max_attempts=2)
    assert "chưa tìm thấy đủ thông tin" in (resp.answer or "")
    assert resp.citations == []


async def test_retry_appends_instruction_only_on_second_call(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    capture: dict = {}
    _patch_synthesize(monkeypatch, used=("ghost-id",), capture=capture)
    await run_ask(AskRequest(question="hỏi", stream=False))
    first_user = capture["calls"][0][1]["content"]
    second_user = capture["calls"][1][1]["content"]
    assert "Lượt tạo trước bị từ chối" not in first_user
    assert "Lượt tạo trước bị từ chối" in second_user


async def test_confidence_insufficient_goes_honest(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, used=("c-1",), confidence="không đủ dữ liệu")
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert resp.confidence == "không đủ dữ liệu"
    assert "chưa tìm thấy đủ thông tin" in (resp.answer or "")


async def test_citation_built_from_chunk_metadata(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    cit = resp.citations[0]
    assert cit.source_file == "lichsu.clean.md"
    assert cit.chunk_index == 42
    assert cit.start_line == 100
    assert cit.end_line == 120
    assert cit.heading_path == ["II", "2.1"]


# --- seed_mentions handoff ---


async def test_seed_mentions_passed_to_retrieve(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="needs_retrieval", entities=["Trương Định"])
    capture: dict = {}
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]), capture=capture)
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    await run_ask(AskRequest(question="Ông ấy làm gì?", stream=False))
    assert capture["seed_mentions"] == ["Trương Định"]
    assert capture["question"] == "standalone q"  # dùng standalone_query đã rewrite


# --- visualization ---


async def test_visualization_present_on_success(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, used=("c-1",))
    payload = VisualizationPayload(
        timeline=[
            TimelineItem(
                event_id="e1", label="x", summary="y", time_start="1864", confidence="cao"
            )
        ],
        event_count=1,
    )
    _patch_viz(monkeypatch, payload)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert resp.visualization is not None
    assert resp.visualization.event_count == 1


async def test_visualization_error_returns_answer_with_warning(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch, error=True)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert resp.answer == "Đáp án."  # answer vẫn trả
    assert resp.visualization is None
    assert any("visualization" in w for w in resp.warnings)


async def test_visualization_empty_still_valid(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch, VisualizationPayload())  # gazetteer rỗng -> no marker
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert resp.visualization is not None
    assert resp.visualization.markers == []


# --- build_query fallback ---


async def test_build_query_llm_error_falls_back_to_needs_retrieval(monkeypatch) -> None:
    _patch_build_query(monkeypatch, error=True)
    capture: dict = {}
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]), capture=capture)
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="Trương Định là ai?", stream=False))
    # fallback: standalone_query = question raw, seed rỗng, route needs_retrieval
    assert capture["question"] == "Trương Định là ai?"
    assert capture["seed_mentions"] == []
    assert any("build_query" in w for w in resp.warnings)


# --- emitter event order (status -> token -> citations -> visualization) ---


async def test_event_order_on_happy_path(monkeypatch) -> None:
    _patch_build_query(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    emitter = ListEmitter()
    await run_ask(AskRequest(question="hỏi", stream=False), emitter=emitter)
    types = [t for t, _ in emitter.events]
    assert types.index("token") < types.index("citations") < types.index("visualization")
    assert types[0] == "status"
