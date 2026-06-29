"""Unit test SSE collector — tái dựng message cuối từ chuỗi event."""

from __future__ import annotations

from app.services.sse_collector import SseCollector


def test_collects_tokens_citations_visualization_done() -> None:
    col = SseCollector()
    col.feed("status", {"node": "retrieve"})
    col.feed("token", {"text": "Trương Định "})
    col.feed("token", {"text": "chống Pháp."})
    col.feed("citations", {"citations": [{"chunk_id": "c1"}, {"chunk_id": "c2"}]})
    col.feed("visualization", {"visualization": {"map": []}})
    col.feed("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})

    assert col.content == "Trương Định chống Pháp."
    assert col.citations == [{"chunk_id": "c1"}, {"chunk_id": "c2"}]
    assert col.visualization == {"map": []}
    assert col.confidence == "cao"
    assert col.retrieval_mode == "hybrid"
    assert col.should_persist()
    fields = col.message_fields()
    assert fields["role"] == "assistant"
    assert fields["content"] == "Trương Định chống Pháp."
    assert fields["clarification_needed"] is False


def test_regenerating_clears_previous_tokens() -> None:
    col = SseCollector()
    col.feed("token", {"text": "câu trả lời cũ"})
    col.feed("regenerating", {})
    col.feed("token", {"text": "câu trả lời mới"})
    col.feed("done", {"confidence": "vừa", "retrieval_mode": "hybrid", "warnings": []})
    assert col.content == "câu trả lời mới"


def test_clarification_persisted_as_content() -> None:
    col = SseCollector()
    col.feed("clarification", {"question": "Bạn hỏi giai đoạn nào?"})
    col.feed("done", {"confidence": None, "retrieval_mode": "none", "warnings": []})
    assert col.should_persist()
    fields = col.message_fields()
    assert fields["clarification_needed"] is True
    assert fields["content"] == "Bạn hỏi giai đoạn nào?"


def test_error_not_persisted() -> None:
    col = SseCollector()
    col.feed("token", {"text": "partial"})
    col.feed("error", {"code": "qdrant_unavailable", "message": "x"})
    assert not col.should_persist()
    assert col.error == {"code": "qdrant_unavailable", "message": "x"}


def test_blocked_not_persisted() -> None:
    col = SseCollector()
    col.feed("blocked", {"reason": "guardrails"})
    assert not col.should_persist()


def test_empty_answer_not_persisted() -> None:
    col = SseCollector()
    col.feed("done", {"confidence": None, "retrieval_mode": "none", "warnings": []})
    assert not col.should_persist()
