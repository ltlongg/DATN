"""Test answer flow qua run_ask với retrieval/LLM/visualization đã mock.

Phủ mọi nhánh: route (needs_retrieval/ambiguous/out_of_scope/smalltalk), has_context
(empty -> honest), citation build từ used_chunk_ids (TẠM BỎ validate/retry, xem
nodes.py::build_visualization), seed handoff (luật §2.1), visualization (ok/error), `plan`
fallback.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.orchestrator import nodes
from app.orchestrator.emitter import ListEmitter
from app.orchestrator.runner import run_ask
from app.schemas.ask import AskRequest, PlanOutput, PlanStep, StepQuery, SynthesizedAnswer
from app.schemas.guardrails import GuardrailDecision
from app.schemas.retrieval import RetrievalBackendError, RetrievalResult, RetrievedChunk
from app.schemas.visualization import TimelineItem, VisualizationPayload


@pytest.fixture(autouse=True)
def _allow_guardrails(monkeypatch):
    """guard_input chạy đầu graph -> mặc định cho qua để test flow hiện có không gọi LLM
    guardrails thật. Test guardrails riêng ở test_guardrails.py."""

    async def allow(question, history, **_kwargs):
        return GuardrailDecision(action="allow")

    monkeypatch.setattr(nodes, "check_input", allow)


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


def _patch_plan(
    monkeypatch, *, route="needs_retrieval", entities=None, error=False, selected_mode="hybrid"
):
    """Mock LLM `plan`. `steps` để rỗng -> normalize_plan dựng 1 bước từ standalone_query,
    tức đúng hành vi mặc định; test nào cần nhiều query thì mock riêng."""
    output = PlanOutput(
        standalone_query="standalone q",
        mentioned_entities=entities or [],
        route=route,
        selected_mode=selected_mode,
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
    async def fake(question, *, seed_mentions=None, **kwargs):
        if capture is not None:
            capture["question"] = question
            capture["seed_mentions"] = seed_mentions
        if error:
            raise error
        return result if result is not None else _retrieval(["c-1"])

    monkeypatch.setattr(nodes, "retrieve_hybrid", fake)


def _patch_synthesize(monkeypatch, *, answer="Đáp án.", used=("c-1",), confidence="cao", capture=None):
    async def fake(
        messages, *, emitter, model, batch_chars, temperature=0.0, client=None, on_usage=None
    ):
        if capture is not None:
            capture.setdefault("calls", []).append(messages)
            capture["temperature"] = temperature
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
    _patch_plan(monkeypatch, route="needs_retrieval")
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
    _patch_plan(monkeypatch, route="ambiguous")

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
    _patch_plan(monkeypatch, route="out_of_scope")
    resp = await run_ask(AskRequest(question="2 + 2 bằng mấy?", stream=False))
    assert resp.retrieval_mode == "none"
    assert resp.confidence == "không đủ dữ liệu"
    assert "chưa tìm thấy đủ thông tin" in (resp.answer or "")


async def test_smalltalk_routes_to_direct_response(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="smalltalk")
    resp = await run_ask(AskRequest(question="Xin chào", stream=False))
    assert resp.retrieval_mode == "none"
    assert "Xin chào" in (resp.answer or "")
    assert "chưa tìm thấy đủ thông tin" not in (resp.answer or "")  # KHÔNG dùng honest message


# --- has_context ---


async def test_empty_retrieval_goes_honest(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval([]))

    async def boom(*a, **k):
        raise AssertionError("synthesize không được gọi khi không có chunk")

    monkeypatch.setattr(nodes, "stream_synthesis", boom)
    resp = await run_ask(AskRequest(question="hỏi gì đó", stream=False))
    assert resp.citations == []
    assert "chưa tìm thấy đủ thông tin" in (resp.answer or "")


# --- dependency error ---


async def test_retrieval_all_backends_fail_propagates(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, error=RetrievalBackendError("all_backends_failed"))
    with pytest.raises(RetrievalBackendError) as exc:
        await run_ask(AskRequest(question="hỏi", stream=False))
    assert exc.value.code == "all_backends_failed"


# --- citation build (TẠM BỎ validate/retry — filter đơn giản, không rẽ honest) ---


# --- B5: validate_citations + after_validate (4 nhánh) ---


def _patch_synthesize_sequence(monkeypatch, rounds, *, capture=None):
    """Mock synthesize trả kết quả KHÁC NHAU theo từng lượt: [(answer, used, confidence)...].
    Cần cho B5 vì lượt soạn lại phải khác lượt đầu mới kiểm được là nó đã soạn lại thật."""
    calls = {"n": 0}

    async def fake(messages, *, emitter, model, batch_chars, temperature=0.0, **_kw):
        answer, used, confidence = rounds[min(calls["n"], len(rounds) - 1)]
        calls["n"] += 1
        if capture is not None:
            capture.setdefault("prompts", []).append(messages)
        await emitter.emit("token", {"text": answer})
        return SynthesizedAnswer(
            answer=answer, used_chunk_ids=list(used), confidence=confidence
        )

    monkeypatch.setattr(nodes, "stream_synthesis", fake)
    return calls


async def test_all_citations_invalid_triggers_exactly_one_retry(monkeypatch) -> None:
    """LLM bịa sạch id -> 0 liên kết hợp lệ -> soạn lại. Trước B5 id bịa bị vứt IM LẶNG và
    câu trả lời vẫn hiện kèm dấu [1] mà khối Nguồn rỗng."""
    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    capture: dict = {}
    calls = _patch_synthesize_sequence(
        monkeypatch,
        [("Bịa.", ("ghost-id",), "cao"), ("Có nguồn.", ("c-1",), "cao")],
        capture=capture,
    )
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert calls["n"] == 2
    assert resp.answer == "Có nguồn."
    assert [c.chunk_id for c in resp.citations] == ["c-1"]
    # Lượt 2 phải dùng prompt is_retry, không phải lặp y nguyên prompt cũ.
    assert capture["prompts"][0] != capture["prompts"][1]


async def test_retry_exhausted_falls_back_to_honest_answer(monkeypatch) -> None:
    """Soạn lại vẫn 0 nguồn -> thà nói chưa đủ dữ liệu còn hơn đưa câu trả lời không có gì
    chống lưng."""
    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    calls = _patch_synthesize_sequence(monkeypatch, [("Bịa.", ("ghost-id",), "cao")])
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert calls["n"] == 2  # dừng đúng ở synthesize_max_attempts, không lặp vô hạn
    assert resp.confidence == "không đủ dữ liệu"
    assert resp.answer == nodes.HONEST_MESSAGE
    assert resp.citations == []


async def test_partially_invalid_citations_keep_the_valid_ones_without_retry(
    monkeypatch,
) -> None:
    """Còn ≥1 id hợp lệ thì ĐI TIẾP — `after_validate` chỉ soạn lại ở ca 0 hợp lệ. Đây là lý
    do dòng phụ trên panel không được viết "soạn lại" cho ca 1/2."""
    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1", "c-2"]))
    calls = _patch_synthesize_sequence(
        monkeypatch, [("Đáp án.", ("ghost-id", "c-2"), "cao")]
    )
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert calls["n"] == 1
    assert resp.answer == "Đáp án."
    assert [c.chunk_id for c in resp.citations] == ["c-2"]


async def test_confidence_insufficient_goes_honest_without_burning_a_retry(
    monkeypatch,
) -> None:
    """LLM tự khai không trả lời được thì soạn lại cũng vô ích -> đi honest luôn. Nhánh này
    phải đứng TRƯỚC nhánh đếm citation trong `after_validate`."""
    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    calls = _patch_synthesize_sequence(
        monkeypatch, [("Đáp án.", ("c-1",), "không đủ dữ liệu")]
    )
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert calls["n"] == 1  # KHÔNG tốn lượt soạn lại
    assert resp.confidence == "không đủ dữ liệu"
    assert resp.answer == nodes.HONEST_MESSAGE
    assert resp.citations == []


async def test_valid_citations_go_straight_through(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    calls = _patch_synthesize_sequence(monkeypatch, [("Đáp án.", ("c-1", "c-1"), "cao")])
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert calls["n"] == 1
    assert [c.chunk_id for c in resp.citations] == ["c-1"]  # dedupe, giữ thứ tự


async def test_citation_built_from_chunk_metadata(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="needs_retrieval")
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


# --- quote kèm citation (citation-viewer-plan Pha 1) ---


def test_make_quote_keeps_short_text_whole() -> None:
    assert nodes._make_quote("Năm 1858, Pháp nổ súng ở Đà Nẵng.") == (
        "Năm 1858, Pháp nổ súng ở Đà Nẵng."
    )


def test_make_quote_collapses_whitespace() -> None:
    assert nodes._make_quote("  Năm 1858\n\nPháp nổ súng.  ") == "Năm 1858 Pháp nổ súng."


def test_make_quote_cuts_long_text_at_word_boundary() -> None:
    text = "Nguyễn " * 100  # dài hơn hẳn CITATION_QUOTE_CHARS
    quote = nodes._make_quote(text)
    assert quote is not None
    assert quote.endswith("…")
    assert len(quote) <= nodes.CITATION_QUOTE_CHARS + 1  # +1 cho dấu "…"
    # Cắt ở ranh giới từ: không đứt giữa chữ, không để lại khoảng trắng thừa trước "…".
    assert quote.removesuffix("…").endswith("Nguyễn")


def test_make_quote_hard_cuts_token_longer_than_limit() -> None:
    # Không có khoảng trắng để cắt -> đành cắt cứng, vẫn phải có "…" báo còn nữa.
    quote = nodes._make_quote("a" * 500)
    assert quote == "a" * nodes.CITATION_QUOTE_CHARS + "…"


@pytest.mark.parametrize("text", ["", "   \n\t  "])
def test_make_quote_blank_text_returns_none(text: str) -> None:
    assert nodes._make_quote(text) is None


async def test_citation_carries_quote_from_chunk_text(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert resp.citations[0].quote == "text c-1"


# --- seed handoff + luật entity §2.1 ---


async def test_seed_from_question_passed_to_retrieve(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="needs_retrieval", entities=["Trương Định"])
    capture: dict = {}
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]), capture=capture)
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    await run_ask(AskRequest(question="Trương Định làm gì?", stream=False))
    assert capture["seed_mentions"] == ["Trương Định"]  # có nguyên văn trong câu hỏi -> giữ
    assert capture["question"] == "standalone q"  # dùng standalone_query đã rewrite


async def test_seed_not_in_question_is_dropped_and_passed_as_none(monkeypatch) -> None:
    """Luật §2.1: entity không có NGUYÊN VĂN trong câu hỏi hiện tại thì loại — kể cả khi
    LLM suy ra đúng từ lịch sử hội thoại.

    Và phải truyền `None` chứ KHÔNG phải `[]`: `match_seed_entities` coi `[]` là "có danh
    sách seed và nó rỗng" -> tắt graph hẳn, còn `None` mới bật fallback token-match từ query.
    """
    _patch_plan(monkeypatch, route="needs_retrieval", entities=["Trương Định"])
    capture: dict = {}
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]), capture=capture)
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="Ông ấy làm gì?", stream=False))
    assert capture["seed_mentions"] is None
    assert any("entity" in w for w in resp.warnings)  # loại phải có warning, không im lặng


# --- visualization ---


async def test_visualization_present_on_success(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="needs_retrieval")
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
    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch, error=True)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert resp.answer == "Đáp án."  # answer vẫn trả
    assert resp.visualization is None
    assert any("visualization" in w for w in resp.warnings)


async def test_visualization_empty_still_valid(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch, VisualizationPayload())  # gazetteer rỗng -> no marker
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert resp.visualization is not None
    assert resp.visualization.markers == []


# --- plan fallback ---


async def test_plan_llm_error_falls_back_to_needs_retrieval(monkeypatch) -> None:
    _patch_plan(monkeypatch, error=True)
    capture: dict = {}
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]), capture=capture)
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="Trương Định là ai?", stream=False))
    # fallback: 1 bước 1 query = câu hỏi raw, không seed, route needs_retrieval
    assert capture["question"] == "Trương Định là ai?"
    assert capture["seed_mentions"] is None
    assert any("plan" in w for w in resp.warnings)


# --- emitter event order (status -> token -> citations -> visualization) ---


async def test_event_order_on_happy_path(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    emitter = ListEmitter()
    await run_ask(AskRequest(question="hỏi", stream=False), emitter=emitter)
    types = [t for t, _ in emitter.events]
    assert types.index("token") < types.index("citations") < types.index("visualization")
    assert types[0] == "status"


# --- dispatch theo mode (user chọn tay 1 trong 3) ---


def _patch_three_retrievers(monkeypatch, called: dict, *, result=None) -> None:
    async def fake_trad(question, **kw):
        called["which"] = "traditional"
        return result if result is not None else _retrieval(["c-1"])

    async def fake_graph(query, **kw):
        called["which"] = "graph"
        return result if result is not None else _retrieval(["c-1"])

    async def fake_hybrid(question, **kw):
        called["which"] = "hybrid"
        return result if result is not None else _retrieval(["c-1"])

    monkeypatch.setattr(nodes, "retrieve_traditional", fake_trad)
    monkeypatch.setattr(nodes, "retrieve_graph", fake_graph)
    monkeypatch.setattr(nodes, "retrieve_hybrid", fake_hybrid)


@pytest.mark.parametrize("mode", ["traditional", "graph", "hybrid"])
async def test_override_mode_wins_over_agent_choice(monkeypatch, mode) -> None:
    # plan CHỌN hybrid, nhưng user ép mode -> override phải thắng.
    _patch_plan(monkeypatch, route="needs_retrieval", selected_mode="hybrid")
    called: dict = {}
    _patch_three_retrievers(monkeypatch, called)
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="hỏi", mode=mode, stream=False))
    assert called["which"] == mode
    assert resp.retrieval_mode == mode


@pytest.mark.parametrize("chosen", ["traditional", "hybrid"])
async def test_auto_mode_uses_agent_choice(monkeypatch, chosen) -> None:
    _patch_plan(monkeypatch, route="needs_retrieval", selected_mode=chosen)
    called: dict = {}
    _patch_three_retrievers(monkeypatch, called)
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))  # không truyền mode -> auto
    assert called["which"] == chosen
    assert resp.retrieval_mode == chosen


async def test_plan_error_falls_back_to_hybrid_in_auto_mode(monkeypatch) -> None:
    _patch_plan(monkeypatch, error=True)
    called: dict = {}
    _patch_three_retrievers(monkeypatch, called)
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="hỏi", stream=False))
    assert called["which"] == "hybrid"  # hybrid là siêu tập -> an toàn nhất khi không biết
    assert resp.retrieval_mode == "hybrid"


async def test_plan_error_still_respects_override(monkeypatch) -> None:
    _patch_plan(monkeypatch, error=True)
    called: dict = {}
    _patch_three_retrievers(monkeypatch, called)
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    await run_ask(AskRequest(question="hỏi", mode="traditional", stream=False))
    assert called["which"] == "traditional"


async def test_graph_empty_suggests_other_mode(monkeypatch) -> None:
    # mode=graph nhưng không ground được seed -> honest gợi ý đổi mode (KHÔNG auto-fallback).
    _patch_plan(monkeypatch, route="needs_retrieval")
    called: dict = {}
    empty = RetrievalResult(mode="graph", query="q", chunks=[])
    _patch_three_retrievers(monkeypatch, called, result=empty)
    resp = await run_ask(AskRequest(question="hỏi", mode="graph", stream=False))
    assert called["which"] == "graph"
    assert resp.retrieval_mode == "graph"
    assert "Traditional" in (resp.answer or "") and "Hybrid" in (resp.answer or "")


async def test_traditional_empty_uses_generic_honest(monkeypatch) -> None:
    # traditional rỗng -> message honest CHUNG (không gợi ý đổi mode, user chỉ yêu cầu graph).
    _patch_plan(monkeypatch, route="needs_retrieval")
    called: dict = {}
    empty = RetrievalResult(mode="traditional", query="q", chunks=[])
    _patch_three_retrievers(monkeypatch, called, result=empty)
    resp = await run_ask(AskRequest(question="hỏi", mode="traditional", stream=False))
    assert "chưa tìm thấy đủ thông tin" in (resp.answer or "")


# --- Phần F: document reordering áp ở synthesize (chống lost-in-the-middle) ---


# --- runtime_config: llm_temperature chảy vào synthesize ---


async def test_llm_temperature_from_runtime_config_reaches_synthesize(monkeypatch) -> None:
    from app.core.runtime_config import RuntimeConfig
    from app.orchestrator import runner

    # Override runtime_config (autouse fixture để mặc định 0.0) -> temperature admin đặt phải
    # đi qua prepare_state -> state["runtime_config"] -> node synthesize -> stream_synthesis.
    monkeypatch.setattr(runner, "get_runtime_config", lambda: RuntimeConfig(llm_temperature=0.7))
    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    capture: dict = {}
    _patch_synthesize(monkeypatch, used=("c-1",), capture=capture)
    _patch_viz(monkeypatch)
    await run_ask(AskRequest(question="hỏi", stream=False))
    assert capture["temperature"] == 0.7


async def test_synthesize_reorders_chunks_in_prompt(monkeypatch) -> None:
    import re

    _patch_plan(monkeypatch, route="needs_retrieval")
    _patch_retrieve(monkeypatch, _retrieval(["c0", "c1", "c2", "c3", "c4"]))
    capture: dict = {}
    _patch_synthesize(monkeypatch, used=("c0",), capture=capture)
    _patch_viz(monkeypatch)
    await run_ask(AskRequest(question="hỏi", stream=False))
    prompt = capture["calls"][0][1]["content"]
    order = re.findall(r"chunk_id: (c\d)", prompt)
    assert order == ["c0", "c2", "c4", "c3", "c1"]  # best ở hai đầu, yếu ở giữa


# --- B1: fan-out nhiều query trong MỘT bước ---


def _patch_plan_with_queries(monkeypatch, queries: list[StepQuery]):
    output = PlanOutput(
        standalone_query="standalone q",
        route="needs_retrieval",
        steps=[PlanStep(id=1, label="Bước 1", queries=queries)],
    )

    async def fake_parse(**kw):
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=output))])

    monkeypatch.setattr(
        nodes,
        "get_async_openai_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=fake_parse))),
    )


async def test_multi_query_step_runs_every_query_and_merges(monkeypatch) -> None:
    """3 query -> 3 lượt retrieve, kết quả gộp dedupe theo chunk_id."""
    _patch_plan_with_queries(
        monkeypatch,
        [
            StepQuery(query="nguyên nhân Yên Thế"),
            StepQuery(query="diễn biến Yên Thế"),
            StepQuery(query="kết quả Yên Thế"),
        ],
    )
    seen: list[str] = []
    per_query = {
        "nguyên nhân Yên Thế": _retrieval(["c-1", "c-2"]),
        "diễn biến Yên Thế": _retrieval(["c-2", "c-3"]),  # c-2 trùng -> phải dedupe
        "kết quả Yên Thế": _retrieval(["c-4"]),
    }

    async def fake(question, *, seed_mentions=None, **kwargs):
        seen.append(question)
        return per_query[question]

    monkeypatch.setattr(nodes, "retrieve_hybrid", fake)
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    resp = await run_ask(AskRequest(question="Yên Thế: nguyên nhân, diễn biến, kết quả?", stream=False))

    assert sorted(seen) == sorted(per_query)  # chạy đủ 3 query
    assert resp.answer == "Đáp án."
    # c-2 đứng đầu: được 2 query trỏ tới nên RRF cross-query cao nhất.
    assert resp.debug is None  # debug=False mặc định -> không lộ ra response


async def test_multi_query_rrf_ranks_chunk_hit_by_two_queries_first(monkeypatch) -> None:
    _patch_plan_with_queries(
        monkeypatch, [StepQuery(query="q1"), StepQuery(query="q2")]
    )
    per_query = {
        "q1": _retrieval(["c-a", "c-shared"]),  # c-shared rank 2
        "q2": _retrieval(["c-b", "c-shared"]),  # c-shared rank 2 lần nữa -> tổng cao nhất
    }

    async def fake(question, *, seed_mentions=None, **kwargs):
        return per_query[question]

    monkeypatch.setattr(nodes, "retrieve_hybrid", fake)
    capture: dict = {}
    _patch_synthesize(monkeypatch, used=("c-shared",), capture=capture)
    _patch_viz(monkeypatch)
    await run_ask(AskRequest(question="hỏi", stream=False))

    import re

    prompt = capture["calls"][0][1]["content"]
    order = re.findall(r"chunk_id: (c-[a-z]+)", prompt)
    # reorder_for_context xếp best-first ra hai đầu -> chunk điểm cao nhất luôn ở vị trí 0.
    assert order[0] == "c-shared"


async def test_plan_caps_queries_per_step(monkeypatch) -> None:
    """LLM trả nhiều query hơn `max_queries_per_step` -> cắt, không chạy hết."""
    monkeypatch.setattr(nodes.get_settings(), "max_queries_per_step", 2, raising=True)
    _patch_plan_with_queries(
        monkeypatch, [StepQuery(query=f"q{i}") for i in range(5)]
    )
    calls: list[str] = []

    async def fake(question, *, seed_mentions=None, **kwargs):
        calls.append(question)
        return _retrieval(["c-1"])

    monkeypatch.setattr(nodes, "retrieve_hybrid", fake)
    _patch_synthesize(monkeypatch, used=("c-1",))
    _patch_viz(monkeypatch)
    await run_ask(AskRequest(question="hỏi", stream=False))
    assert calls == ["q0", "q1"]
