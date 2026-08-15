"""Test contract /ask: bounds của request, default response, structured-output schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.ask import (
    AskRequest,
    AskResponse,
    PlanOutput,
    PlanStep,
    ChatMessage,
    StepQuery,
    StepResolveOutput,
    SynthesizedAnswer,
)

def test_ask_request_defaults() -> None:
    req = AskRequest(question="Trương Định là ai?")
    assert req.history == []
    assert req.stream is True
    assert req.debug is False

def test_ask_request_rejects_empty_question() -> None:
    with pytest.raises(ValidationError):
        AskRequest(question="")

def test_ask_request_rejects_too_long_history() -> None:
    msgs = [ChatMessage(role="user", content="x") for _ in range(13)]
    with pytest.raises(ValidationError):
        AskRequest(question="hỏi gì đó", history=msgs)

def test_ask_request_accepts_history_at_limit() -> None:
    msgs = [ChatMessage(role="user", content="x") for _ in range(12)]
    req = AskRequest(question="hỏi", history=msgs)
    assert len(req.history) == 12

def test_chat_message_rejects_empty_content() -> None:
    with pytest.raises(ValidationError):
        ChatMessage(role="user", content="")

def test_ask_response_defaults() -> None:
    resp = AskResponse()
    assert resp.clarification_needed is False
    assert resp.answer is None
    assert resp.citations == []
    assert resp.retrieval_mode == "none"
    assert resp.confidence is None
    assert resp.visualization is None
    assert resp.warnings == []

def test_plan_output_defaults() -> None:
    out = PlanOutput(standalone_query="q", route="needs_retrieval")
    assert out.mentioned_entities == []

def test_plan_step_defaults_to_no_resolve() -> None:
    """Bước KHÔNG khai `resolve` là bước chỉ truy hồi — không tốn LLM call nào (§2)."""
    step = PlanStep(id=1, label="L", queries=[StepQuery(query="q")])
    assert step.resolve == ""
    assert step.depends_on is None

def test_step_resolve_output_defaults_to_not_found() -> None:
    """Default phải là "không trích được" + confidence thấp: LLM trả thiếu field thì hệ
    thống dừng list, KHÔNG đi tiếp với giá trị rỗng tưởng là hợp lệ (§4.4)."""
    out = StepResolveOutput()
    assert out.value == ""
    assert out.confidence == "thấp"
    assert out.source_chunk_ids == []

def test_synthesized_answer_field_order_answer_first() -> None:
    # answer phải là field đầu để stream ra trước used_chunk_ids/confidence.
    assert list(SynthesizedAnswer.model_fields) == ["answer", "used_chunk_ids", "confidence"]
