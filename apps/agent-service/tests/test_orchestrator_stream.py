"""Test run_ask_stream (SSE): thứ tự event, token chỉ trong synthesize, clarify không
token, lỗi sau khi mở SSE đi qua event error.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.orchestrator import nodes
from app.orchestrator.runner import run_ask_stream
from app.schemas.ask import (
    AskRequest,
    PlanOutput,
    PlanStep,
    StepQuery,
    StepResolveOutput,
    SynthesizedAnswer,
)
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

def _patch_plan(monkeypatch, *, route="needs_retrieval", steps=None, resolve=None):
    """`resolve` = hàng đợi output cho `resolve_step`; phân biệt với `plan` bằng
    `response_format`, đúng cách node thật phân biệt."""
    output = PlanOutput(
        standalone_query="q", mentioned_entities=[], route=route, steps=list(steps or [])
    )
    resolve_queue = list(resolve or [])

    async def fake_parse(**kw):
        parsed = output
        if kw.get("response_format") is StepResolveOutput:
            assert resolve_queue, "resolve_step gọi nhiều hơn số output đã mock"
            parsed = resolve_queue.pop(0)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(parsed=parsed))])

    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=fake_parse)))
    monkeypatch.setattr(nodes, "get_async_openai_client", lambda: client)

def _patch_retrieve(monkeypatch, result=None, *, error=None, results=None):
    queue = list(results or [])

    async def fake(question, *, seed_mentions=None, **kwargs):
        if error:
            raise error
        if queue:
            return queue.pop(0)
        return result if result is not None else _retrieval(["c-1"])

    monkeypatch.setattr(nodes, "retrieve_hybrid", fake)

def _patch_synthesize(monkeypatch, *, answer="Đáp án ngắn.", used=("c-1",), confidence="cao"):
    async def fake(
        messages, *, emitter, model, batch_chars, reasoning_effort="low", client=None,
        on_usage=None,
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
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    types = [t for t, _ in events]
    assert types[0] == "status"
    assert types[-1] == "done"
    assert types.index("token") < types.index("citations") < types.index("visualization") < types.index("done")

async def test_token_concatenates_to_answer(monkeypatch) -> None:
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, answer="Câu một. Câu hai.")
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    tokens = [d["text"] for t, d in events if t == "token"]
    assert "".join(tokens) == "Câu một. Câu hai."

async def test_done_summary_carries_confidence_and_mode(monkeypatch) -> None:
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch, confidence="vừa")
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    done = next(d for t, d in events if t == "done")
    assert done["confidence"] == "vừa"
    assert done["retrieval_mode"] == "hybrid"

async def test_insufficient_confidence_with_valid_citation_keeps_streamed_answer(
    monkeypatch,
) -> None:
    """Self-reported confidence không được xoá answer đã có nguồn hợp lệ."""
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(
        monkeypatch,
        answer="Phần có căn cứ. Một lời lưu ý tự nhiên về phần còn thiếu.",
        confidence="không đủ dữ liệu",
    )
    _patch_viz(monkeypatch)

    events = await _collect(AskRequest(question="hỏi", stream=True))

    assert "regenerating" not in [t for t, _ in events]
    assert "".join(d["text"] for t, d in events if t == "token") == (
        "Phần có căn cứ. Một lời lưu ý tự nhiên về phần còn thiếu."
    )
    done = next(d for t, d in events if t == "done")
    assert done["confidence"] == "không đủ dữ liệu"

async def test_clarify_emits_clarification_and_done_no_token(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="ambiguous")
    events = await _collect(AskRequest(question="Ông ấy là ai?", stream=True))
    types = [t for t, _ in events]
    assert "clarification" in types
    assert types[-1] == "done"
    assert "token" not in types
    clar = next(d for t, d in events if t == "clarification")
    assert clar["question"]

async def test_error_after_sse_open_goes_through_error_event(monkeypatch) -> None:
    _patch_plan(monkeypatch)
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
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True, debug=True))
    types = [t for t, _ in events]
    assert types[-1] == "done"
    assert types[-2] == "debug"  # debug ngay trước done (gom rồi bắn 1 lần ở cuối)
    dbg = next(d for t, d in events if t == "debug")["debug"]
    # state["debug"] đã tích lũy plan + retrieve qua reducer _merge_debug.
    assert "plan" in dbg and "retrieve" in dbg

async def test_debug_event_absent_when_not_requested(monkeypatch) -> None:
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True, debug=False))
    assert "debug" not in [t for t, _ in events]

async def test_smalltalk_streams_token_and_done(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="smalltalk")
    events = await _collect(AskRequest(question="Xin chào", stream=True))
    types = [t for t, _ in events]
    assert "token" in types
    assert types[-1] == "done"
    tokens = "".join(d["text"] for t, d in events if t == "token")
    assert "Xin chào" in tokens

# --- panel tiến trình (B3, plan §7.3.1) ---

def _steps_event(events) -> list[dict]:
    return next(d for t, d in events if t == "steps")["steps"]

def _step_updates(events) -> list[tuple[str, str]]:
    """(id, state) theo đúng thứ tự phát — thứ tự là một phần của hợp đồng."""
    return [(d["id"], d["state"]) for t, d in events if t == "step"]

async def test_steps_declares_five_rows_for_simple_question(monkeypatch) -> None:
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    assert [r["id"] for r in _steps_event(events)] == [
        "plan",
        "todo:1",
        "synthesize:1",
        "validate:1",
        "visualization",
    ]

async def test_step_updates_follow_the_run_order(monkeypatch) -> None:
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    # `_patch_viz` trả payload RỖNG -> 0 sự kiện -> `partial`, không phải `done`.
    assert _step_updates(events) == [
        ("plan", "done"),
        ("todo:1", "running"),
        ("todo:1", "done"),
        ("synthesize:1", "running"),
        ("synthesize:1", "done"),
        ("validate:1", "done"),
        ("visualization", "running"),
        ("visualization", "partial"),
    ]

async def test_internals_ride_along_with_the_step_that_produced_them(monkeypatch) -> None:
    """Tầng 2 đi NGAY trong event `step`, không gom một lần sát `done` như event `debug` cũ.
    Chính cách gom muộn đó đẻ ra mấy dòng "Đang xử lý…" kẹt vĩnh viễn ở nhánh không chạy tới.
    """
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    with_internals = {
        d["id"] for t, d in events if t == "step" and d.get("internals")
    }
    assert with_internals == {"plan", "todo:1", "synthesize:1", "validate:1", "visualization"}
    # ... và tới TRƯỚC token đầu tiên với những bước chạy trước synthesize.
    types = [t for t, _ in events]
    first_internal = next(
        i for i, (t, d) in enumerate(events) if t == "step" and d.get("internals")
    )
    assert first_internal < types.index("token")

async def test_running_update_carries_no_internals_yet(monkeypatch) -> None:
    """Lúc mở bước thì chưa có số liệu nào — gửi mảng rỗng là mời frontend vẽ bảng trống."""
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    running = [d for t, d in events if t == "step" and d["state"] == "running"]
    assert running and all("internals" not in d for d in running)

MULTIHOP_STEPS = [
    PlanStep(
        id=1,
        label="Xác định người kế nhiệm",
        queries=[StepQuery(query="ai kế nhiệm")],
        resolve="tên người kế nhiệm",
    ),
    PlanStep(
        id=2,
        label="Việc người đó làm sau đó",
        depends_on=1,
        queries=[StepQuery(query="<1> làm gì sau đó")],
    ),
]

async def test_multihop_step_stays_running_until_the_link_is_resolved(monkeypatch) -> None:
    """Bước 1 chốt `done` ở `resolve_step` chứ không ở `retrieve` — giữa hai mốc đó nó vẫn
    đang chạy thật, và panel phải nói đúng như vậy."""
    _patch_plan(
        monkeypatch,
        steps=MULTIHOP_STEPS,
        # `source_chunk_ids` phải trỏ vào chunk CÓ THẬT trong ngữ cảnh bước 1 ("c-1"): mắt
        # xích không có nguồn hợp lệ nào bị loại, dù confidence "cao" (xem resolve_step).
        resolve=[
            StepResolveOutput(
                value="Đề Thám", confidence="cao", source_chunk_ids=["c-1"]
            )
        ],
    )
    _patch_retrieve(monkeypatch, results=[_retrieval(["c-1"]), _retrieval(["c-2"])])
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))

    assert [r["id"] for r in _steps_event(events)] == [
        "plan",
        "todo:1",
        "todo:2",
        "synthesize:1",
        "validate:1",
        "visualization",
    ]
    assert _step_updates(events)[:5] == [
        ("plan", "done"),
        ("todo:1", "running"),  # mở bước
        ("todo:1", "running"),  # tìm xong nhưng CHƯA chốt: còn phải trích mắt xích
        ("todo:1", "done"),  # resolve_step mới là chỗ chốt
        ("todo:2", "running"),
    ]
    resolved = [
        d for t, d in events if t == "step" and d["id"] == "todo:1" and d["state"] == "done"
    ]
    assert resolved[0]["detail"] == "Xác định người kế nhiệm → Đề Thám"

async def test_unresolved_link_marks_remaining_steps_skipped(monkeypatch) -> None:
    """Dừng list thì các bước còn lại phải nói rõ là ĐÃ BỊ BỎ. Để chúng ở `pending` thì sau
    khi stream đóng, "hệ thống cân nhắc rồi bỏ" trông y hệt "chưa chạy tới"."""
    _patch_plan(
        monkeypatch,
        steps=MULTIHOP_STEPS,
        resolve=[StepResolveOutput(value="", confidence="thấp")],
    )
    _patch_retrieve(monkeypatch, results=[_retrieval(["c-1"])])
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))

    updates = _step_updates(events)
    assert ("todo:1", "partial") in updates
    assert ("todo:2", "skipped") in updates
    assert ("synthesize:1", "done") in updates  # vẫn trả lời bằng phần đã tìm được

async def test_zero_chunk_at_resolve_step_skips_the_rest_without_calling_llm(
    monkeypatch,
) -> None:
    _patch_plan(monkeypatch, steps=MULTIHOP_STEPS, resolve=[])
    _patch_retrieve(monkeypatch, results=[_retrieval([])])
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))

    updates = _step_updates(events)
    assert ("todo:1", "partial") in updates
    assert ("todo:2", "skipped") in updates

async def test_smalltalk_has_no_placeholder_steps_left_hanging(monkeypatch) -> None:
    """Ca trong ảnh bug: DebugPanel cũ hiện "Đang xử lý…" vĩnh viễn cho Truy hồi/Đối chiếu vì
    những node đó không bao giờ chạy. Panel chỉ khai dòng THẬT SỰ có trong kịch bản."""
    _patch_plan(monkeypatch, route="smalltalk")
    events = await _collect(AskRequest(question="chào", stream=True))
    assert [r["id"] for r in _steps_event(events)] == ["plan"]
    plan_update = next(d for t, d in events if t == "step" and d["id"] == "plan")
    assert plan_update["detail"] == "Câu xã giao · không cần tra tài liệu"
    assert any(r["label"] == "Định tuyến" for r in plan_update["internals"])

async def test_visualization_failure_names_the_error_instead_of_going_quiet(
    monkeypatch,
) -> None:
    """Đã cắn một lần: bảng chưa tồn tại -> UndefinedTable nuốt sạch timeline mà panel
    không hé nửa lời (xem CLAUDE.md)."""
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)

    def boom(ids):
        raise RuntimeError("viz down")

    monkeypatch.setattr(nodes, "build_visualization_payload", boom)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    viz = [d for t, d in events if t == "step" and d["id"] == "visualization"][-1]
    assert viz["state"] == "partial"
    assert viz["detail"] == "Không dựng được"
    assert viz["internals"] == [{"label": "Lỗi", "value": "RuntimeError"}]
    # Câu trả lời vẫn về đủ — viz hỏng không được làm fail answer.
    assert any(t == "done" for t, _ in events)

async def test_steps_arrives_before_any_step_update_and_before_first_token(
    monkeypatch,
) -> None:
    """Frontend chỉ nhận `step` cho id đã khai báo -> `steps` phải tới trước, nếu không
    mọi cập nhật đầu tiên bị bỏ im lặng."""
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    types = [t for t, _ in await _collect(AskRequest(question="hỏi", stream=True))]
    assert types.index("steps") < types.index("step") < types.index("token")

async def test_retrieve_detail_reports_chunk_count(monkeypatch) -> None:
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1", "c-2", "c-3"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    detail = next(d for t, d in events if t == "step" and d["id"] == "todo:1" and "detail" in d)
    assert detail["detail"] == "Dense + BM25 + graph · 3 đoạn"

async def test_zero_chunks_marks_both_retrieve_and_synthesize_partial(monkeypatch) -> None:
    """0 chunk -> has_context đưa sang honest_answer: bước tìm `partial`, và bước soạn bài
    KHÔNG được treo vĩnh viễn ở `pending` mà phải nói rõ vì sao không chạy.

    Dòng `validate:1` thì NGƯỢC LẠI — nó thật sự không chạy, nên phải ở lại `pending`; bịa
    cho nó một kết quả là nói dối về việc hệ thống đã làm."""
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval([]))
    events = await _collect(AskRequest(question="hỏi", stream=True))
    updates = _step_updates(events)
    assert updates == [
        ("plan", "done"),
        ("todo:1", "running"),
        ("todo:1", "partial"),
        ("synthesize:1", "partial"),
    ]
    assert not any(sid.startswith("validate:") for sid, _ in updates)

async def test_clarify_declares_only_plan_row(monkeypatch) -> None:
    _patch_plan(monkeypatch, route="ambiguous")
    events = await _collect(AskRequest(question="Ông ấy là ai?", stream=True))
    assert [r["id"] for r in _steps_event(events)] == ["plan"]
    assert _step_updates(events) == [("plan", "done")]

async def test_plan_llm_failure_marks_plan_partial_not_done(monkeypatch) -> None:
    """Fallback chạy bằng nguyên câu hỏi -> tick xanh ở đây là nói dối về việc vừa làm."""

    async def boom(**kw):
        raise RuntimeError("llm down")

    monkeypatch.setattr(
        nodes,
        "get_async_openai_client",
        lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(parse=boom))),
    )
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_synthesize(monkeypatch)
    _patch_viz(monkeypatch)
    events = await _collect(AskRequest(question="hỏi", stream=True))
    assert _step_updates(events)[0] == ("plan", "partial")
    assert [r["id"] for r in _steps_event(events)] == [
        "plan",
        "todo:1",
        "synthesize:1",
        "validate:1",
        "visualization",
    ]

async def test_retrieval_backend_error_leaves_row_running_for_frontend_to_close(
    monkeypatch,
) -> None:
    """§7.3.1 mục 5: không có event mới cho ca lỗi — dòng ở lại `running`, frontend hạ
    xuống `partial` khi stream đóng mà chưa có kết."""
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, error=RetrievalBackendError("all_backends_failed"))
    events = await _collect(AskRequest(question="hỏi", stream=True))
    assert _step_updates(events) == [("plan", "done"), ("todo:1", "running")]
    assert [t for t, _ in events][-1] == "error"

async def test_retry_grows_the_panel_with_new_rows(monkeypatch) -> None:
    """Soạn lại (B5) phải HIỆN RA trên panel: thêm `synthesize:2`/`validate:2`, không ghi đè
    dòng cũ. `steps` được phát lại với danh sách dài hơn nên bên nhận phải merge theo id."""
    _patch_plan(monkeypatch)
    _patch_retrieve(monkeypatch, _retrieval(["c-1"]))
    _patch_viz(monkeypatch)
    calls = {"n": 0}

    async def fake(messages, *, emitter, model, batch_chars, reasoning_effort="low", **_kw):
        from app.orchestrator.synthesis import emit_text_as_batches

        calls["n"] += 1
        used = ["ghost-id"] if calls["n"] == 1 else ["c-1"]
        await emit_text_as_batches("Đáp án.", emitter, batch_chars)
        return SynthesizedAnswer(answer="Đáp án.", used_chunk_ids=used, confidence="cao")

    monkeypatch.setattr(nodes, "stream_synthesis", fake)
    events = await _collect(AskRequest(question="hỏi", stream=True))

    declarations = [d["steps"] for t, d in events if t == "steps"]
    assert len(declarations) == 2  # lần 2 phát khi vào lượt soạn lại
    assert [r["id"] for r in declarations[-1]] == [
        "plan",
        "todo:1",
        "synthesize:1",
        "validate:1",
        "synthesize:2",
        "validate:2",
        "visualization",
    ]
    assert _step_updates(events)[-6:] == [
        ("validate:1", "partial"),
        ("synthesize:2", "running"),
        ("synthesize:2", "done"),
        ("validate:2", "done"),
        ("visualization", "running"),
        ("visualization", "partial"),
    ]
    # Dòng phụ nói đúng chuyện đã xảy ra, và chỉ ca 0 hợp lệ mới được ghi "soạn lại".
    v1 = next(d for t, d in events if t == "step" and d["id"] == "validate:1")
    v2 = next(d for t, d in events if t == "step" and d["id"] == "validate:2")
    assert v1["detail"] == "0/1 liên kết nguồn hợp lệ · soạn lại"
    assert v2["detail"] == "1/1 liên kết nguồn hợp lệ"
    assert "regenerating" in [t for t, _ in events]  # frontend xoá chữ lượt 1
