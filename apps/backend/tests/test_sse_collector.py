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


# --- panel tiến trình (B3) ---


def _run_steps(col: SseCollector) -> None:
    col.feed(
        "steps",
        {
            "steps": [
                {"id": "plan", "label": "Phân tích câu hỏi", "kind": "system"},
                {"id": "todo:1", "label": "Tìm A", "kind": "retrieve"},
                {"id": "synthesize:1", "label": "Soạn câu trả lời", "kind": "system"},
            ]
        },
    )
    col.feed("step", {"id": "plan", "state": "done", "detail": "Câu hỏi đơn · 1 bước"})
    col.feed("step", {"id": "todo:1", "state": "running"})
    col.feed("step", {"id": "todo:1", "state": "done", "detail": "Dense + BM25 + graph · 8 đoạn"})


def test_steps_declares_rows_as_pending_until_a_step_update_arrives() -> None:
    col = SseCollector()
    col.feed("steps", {"steps": [{"id": "plan", "label": "L", "kind": "system"}]})
    assert col.steps == [{"id": "plan", "label": "L", "kind": "system", "state": "pending"}]


def test_step_updates_merge_into_the_declared_row() -> None:
    col = SseCollector()
    _run_steps(col)
    by_id = {r["id"]: r for r in col.steps}
    assert by_id["plan"]["state"] == "done"
    assert by_id["plan"]["detail"] == "Câu hỏi đơn · 1 bước"
    assert by_id["todo:1"]["detail"] == "Dense + BM25 + graph · 8 đoạn"
    assert by_id["synthesize:1"]["state"] == "pending"  # chưa chạy tới


def test_step_for_unknown_id_is_ignored() -> None:
    """Cùng luật với frontend: không mọc dòng ma từ id không khai báo."""
    col = SseCollector()
    col.feed("steps", {"steps": [{"id": "plan", "label": "L", "kind": "system"}]})
    col.feed("step", {"id": "todo:9", "state": "done"})
    assert [r["id"] for r in col.steps] == ["plan"]


def test_running_row_is_closed_out_to_partial_when_persisting() -> None:
    """Stream đóng mà dòng còn `running` = không bao giờ có kết -> lưu `partial`, nếu không
    reload ra spinner quay mãi."""
    col = SseCollector()
    _run_steps(col)
    col.feed("step", {"id": "synthesize:1", "state": "running"})
    col.feed("token", {"text": "x"})
    col.feed("done", {"confidence": "cao", "retrieval_mode": "hybrid", "warnings": []})
    saved = {r["id"]: r["state"] for r in col.message_fields()["steps"]}
    assert saved == {"plan": "done", "todo:1": "done", "synthesize:1": "partial"}


def test_skipped_row_survives_persistence_unchanged() -> None:
    """`skipped` (todo list dừng sớm — B4) KHÔNG bị hạ như `running`: nó đã là trạng thái
    cuối cùng và mang nghĩa riêng ("hệ thống bỏ bước này"), hạ xuống `partial` là nói dối
    rằng bước đó có chạy dở."""
    col = SseCollector()
    col.feed(
        "steps",
        {
            "steps": [
                {"id": "todo:1", "label": "Xác định mắt xích", "kind": "retrieve"},
                {"id": "todo:2", "label": "Tra tiếp", "kind": "retrieve"},
            ]
        },
    )
    col.feed("step", {"id": "todo:1", "state": "partial", "detail": "Chưa xác định được X"})
    col.feed("step", {"id": "todo:2", "state": "skipped"})
    col.feed("token", {"text": "x"})
    col.feed("done", {"confidence": "vừa", "retrieval_mode": "hybrid", "warnings": []})
    saved = {r["id"]: r["state"] for r in col.message_fields()["steps"]}
    assert saved == {"todo:1": "partial", "todo:2": "skipped"}


def test_close_out_does_not_mutate_collector_state() -> None:
    col = SseCollector()
    col.feed("steps", {"steps": [{"id": "plan", "label": "L", "kind": "system"}]})
    col.feed("step", {"id": "plan", "state": "running"})
    col.feed("token", {"text": "x"})
    col.feed("done", {"confidence": None, "retrieval_mode": "none", "warnings": []})
    assert col.message_fields()["steps"] == col.message_fields()["steps"]
    assert col.steps[0]["state"] == "running"  # nguồn gốc giữ nguyên


def test_clarification_message_still_persists_its_steps() -> None:
    col = SseCollector()
    col.feed("steps", {"steps": [{"id": "plan", "label": "Phân tích câu hỏi", "kind": "system"}]})
    col.feed("step", {"id": "plan", "state": "done", "detail": "Câu hỏi chưa rõ · cần hỏi lại"})
    col.feed("clarification", {"question": "Bạn hỏi về ai?"})
    fields = col.message_fields()
    assert fields["clarification_needed"] is True
    assert fields["steps"][0]["detail"] == "Câu hỏi chưa rõ · cần hỏi lại"


def test_retry_declaration_keeps_states_of_rows_already_finished() -> None:
    """Lượt soạn lại (B5) phát lại `steps` với danh sách DÀI HƠN. Thay thế thay vì merge thì
    `plan`/`todo:1` đang `done` bị đạp về `pending` -> reload mất sạch chuyện đã xảy ra."""
    def declare(*ids: str) -> dict:
        return {"steps": [{"id": i, "label": i, "kind": "system"} for i in ids]}

    col = SseCollector()
    col.feed("steps", declare("plan", "todo:1", "synthesize:1", "validate:1"))
    col.feed("step", {"id": "plan", "state": "done", "detail": "Câu hỏi đơn · 1 bước"})
    col.feed("step", {"id": "todo:1", "state": "done", "detail": "8 đoạn"})
    col.feed("step", {"id": "synthesize:1", "state": "done", "detail": "Soạn từ 8 đoạn"})
    col.feed(
        "step",
        {"id": "validate:1", "state": "partial", "detail": "0/1 liên kết nguồn hợp lệ · soạn lại"},
    )
    # Vào lượt soạn lại: agent phát lại danh sách, dài thêm 2 dòng.
    col.feed(
        "steps",
        declare("plan", "todo:1", "synthesize:1", "validate:1", "synthesize:2", "validate:2"),
    )
    by_id = {r["id"]: r for r in col.steps}
    assert by_id["plan"]["state"] == "done"
    assert by_id["todo:1"]["detail"] == "8 đoạn"
    assert by_id["validate:1"]["detail"] == "0/1 liên kết nguồn hợp lệ · soạn lại"
    assert by_id["synthesize:2"]["state"] == "pending"  # dòng mới, chưa chạy
    assert "detail" not in by_id["synthesize:2"]


# --- internals (tầng 2 panel tiến trình) ---


def test_step_internals_are_kept_for_persistence() -> None:
    """Collector nhận internals của MỌI lượt, kể cả người dùng thường: bản lưu phải đủ để
    admin soi lại hội thoại của người khác. Việc giấu khỏi người đang hỏi là của api/chat.py."""
    col = SseCollector()
    col.feed("steps", {"steps": [{"id": "plan", "label": "L", "kind": "system"}]})
    col.feed(
        "step",
        {
            "id": "plan",
            "state": "done",
            "detail": "Câu hỏi đơn · 1 bước",
            "internals": [{"label": "Định tuyến", "value": "needs_retrieval"}],
        },
    )
    assert col.message_fields()["steps"][0]["internals"] == [
        {"label": "Định tuyến", "value": "needs_retrieval"}
    ]


def test_retry_declaration_does_not_wipe_internals_of_finished_rows() -> None:
    """Cùng lý do với `detail`: bản `steps` phát lại chỉ mang id/label/kind, không chép sang
    là tầng 2 của mọi bước đã chạy xong biến mất khỏi bản lưu."""
    def declare(*ids: str) -> dict:
        return {"steps": [{"id": i, "label": i, "kind": "system"} for i in ids]}

    col = SseCollector()
    col.feed("steps", declare("plan", "synthesize:1"))
    col.feed(
        "step",
        {"id": "plan", "state": "done", "internals": [{"label": "Model", "value": "m"}]},
    )
    col.feed("steps", declare("plan", "synthesize:1", "synthesize:2"))
    by_id = {r["id"]: r for r in col.steps}
    assert by_id["plan"]["internals"] == [{"label": "Model", "value": "m"}]
    assert "internals" not in by_id["synthesize:2"]
