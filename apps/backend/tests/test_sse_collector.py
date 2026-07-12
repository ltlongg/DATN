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


def test_ttft_keeps_first_mark_and_survives_regenerating() -> None:
    """TTFT chốt ở chữ ĐẦU TIÊN người dùng thấy: mark sau không ghi đè, `regenerating` xoá
    token nhưng KHÔNG xoá mốc (người dùng đã chờ đúng chừng đó rồi)."""
    col = SseCollector()
    col.mark_first_token(1200)
    col.feed("token", {"text": "câu cũ"})
    col.feed("regenerating", {})
    col.mark_first_token(9999)
    col.feed("token", {"text": "câu mới"})
    col.feed("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})
    assert col.ttft_ms == 1200
    assert col.message_fields()["ttft_ms"] == 1200


def test_ttft_none_when_no_token() -> None:
    col = SseCollector()
    col.feed("clarification", {"question": "Bạn hỏi giai đoạn nào?"})
    assert col.ttft_ms is None
    assert col.message_fields()["ttft_ms"] is None


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


def test_blocked_without_content_not_persisted() -> None:
    col = SseCollector()
    col.feed("blocked", {"stage": "input", "categories": ["prompt_injection"]})
    assert col.blocked
    assert not col.should_persist()


def test_blocked_with_safe_message_persisted() -> None:
    # Guardrails chặn: agent stream safe message qua token TRƯỚC blocked -> lưu như assistant
    # message thường (frontend thấy lại khi reload).
    col = SseCollector()
    col.feed("token", {"text": "Xin lỗi, mình không hỗ trợ yêu cầu này."})
    col.feed("blocked", {"stage": "input", "categories": ["harmful_instructions"]})
    assert col.blocked
    assert col.should_persist()
    fields = col.message_fields()
    assert fields["role"] == "assistant"
    assert fields["content"] == "Xin lỗi, mình không hỗ trợ yêu cầu này."
    assert fields["clarification_needed"] is False


def test_empty_answer_not_persisted() -> None:
    col = SseCollector()
    col.feed("done", {"confidence": None, "retrieval_mode": "none", "warnings": []})
    assert not col.should_persist()
