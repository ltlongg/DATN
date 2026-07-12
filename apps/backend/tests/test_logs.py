"""Module 4 — Hội thoại & chất lượng: quality_service thuần (không DB) + endpoints
(Postgres thật, cô lập bằng txn rollback; lọc theo email test / delta để tất định dù DB
có sẵn conversation/message thật).
"""

from __future__ import annotations

from app.models.conversation import add_message, create_conversation
from app.services.quality_service import compute_quality_summary

_TEACHER_EMAIL = "teacher-test@example.com"


# --- pure compute_quality_summary ------------------------------------------


def _asst(
    *,
    retrieval_mode="hybrid",
    citations=None,
    confidence=None,
    clarification=False,
    warnings=None,
    ttft_ms=None,
):
    return {
        "retrieval_mode": retrieval_mode,
        "citations": citations or [],
        "confidence": confidence,
        "clarification_needed": clarification,
        "warnings": warnings or [],
        "ttft_ms": ttft_ms,
    }


def test_quality_summary_no_citation_only_counts_retrieval_attempted() -> None:
    rows = [
        _asst(retrieval_mode="hybrid", citations=[{"chunk_id": "c"}], confidence="cao"),
        _asst(retrieval_mode="hybrid", citations=[], confidence="vừa"),  # no_citation
        # route clarify/smalltalk/out_of_scope: mode="none" + citations=[] -> BÌNH THƯỜNG,
        # KHÔNG tính no_citation.
        _asst(retrieval_mode="none", citations=[], clarification=True),
    ]
    s = compute_quality_summary(rows)
    assert s.total_assistant_messages == 3
    assert s.retrieval_attempted_count == 2
    assert s.no_citation_count == 1  # chỉ message hybrid rỗng citation
    assert s.clarification_count == 1  # đếm toàn bộ, bất kể route


def test_quality_summary_low_confidence_and_warning_count_all_rows() -> None:
    rows = [
        _asst(retrieval_mode="hybrid", citations=[{"c": 1}], confidence="thấp"),
        _asst(retrieval_mode="none", confidence="không đủ dữ liệu"),
        _asst(retrieval_mode="hybrid", citations=[{"c": 1}], warnings=["w"]),
    ]
    s = compute_quality_summary(rows)
    assert s.low_confidence_count == 2  # "thấp" + "không đủ dữ liệu", cả route none
    assert s.warning_count == 1


def test_quality_summary_empty() -> None:
    s = compute_quality_summary([])
    assert s.total_assistant_messages == 0 and s.no_citation_count == 0
    assert s.ttft_measured_count == 0
    assert s.avg_ttft_ms is None and s.p95_ttft_ms is None


def test_quality_summary_ttft_ignores_unmeasured_rows() -> None:
    # Message không đo được TTFT (ttft_ms None) KHÔNG kéo trung bình xuống — mẫu số riêng.
    rows = [
        _asst(ttft_ms=1000),
        _asst(ttft_ms=3000),
        _asst(ttft_ms=None),
    ]
    s = compute_quality_summary(rows)
    assert s.total_assistant_messages == 3
    assert s.ttft_measured_count == 2
    assert s.avg_ttft_ms == 2000
    assert s.p95_ttft_ms == 3000  # nearest-rank trên 2 giá trị -> lớn nhất


# --- endpoints --------------------------------------------------------------


def test_list_conversations_admin_filter_by_email(client, auth, db_conn, users) -> None:  # type: ignore[no-untyped-def]
    teacher = users["teacher"]
    conv = create_conversation(teacher.id, "Cuộc trò chuyện test")
    add_message(conv.id, "user", "câu hỏi")
    add_message(conv.id, "assistant", "trả lời", retrieval_mode="hybrid")
    r = client.get(
        "/api/admin/logs/conversations",
        params={"user_email": _TEACHER_EMAIL},
        headers=auth("admin"),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 1  # chỉ conversation của teacher test (lọc email tất định)
    item = body["items"][0]
    assert item["user_email"] == _TEACHER_EMAIL
    assert item["user_name"] == "Teacher Test"
    assert item["message_count"] == 2


def test_conversation_detail_admin_with_quality_flags(client, auth, db_conn, users) -> None:  # type: ignore[no-untyped-def]
    teacher = users["teacher"]
    conv = create_conversation(teacher.id, "t")
    add_message(conv.id, "user", "câu hỏi")
    add_message(
        conv.id,
        "assistant",
        "đáp",
        retrieval_mode="hybrid",
        citations=[],
        confidence="thấp",
    )
    r = client.get(f"/api/admin/logs/conversations/{conv.id}", headers=auth("admin"))
    assert r.status_code == 200
    body = r.json()
    assert body["user_email"] == _TEACHER_EMAIL
    user_msg, asst_msg = body["messages"]
    assert user_msg["quality"]["retrieval_attempted"] is False  # user message -> False
    # assistant hybrid + citations rỗng -> no_citation + low_confidence.
    assert asst_msg["quality"]["retrieval_attempted"] is True
    assert asst_msg["quality"]["no_citation"] is True
    assert asst_msg["quality"]["low_confidence"] is True


def test_conversation_detail_admin_404(client, auth) -> None:  # type: ignore[no-untyped-def]
    r = client.get(
        "/api/admin/logs/conversations/00000000-0000-0000-0000-000000000000",
        headers=auth("admin"),
    )
    assert r.status_code == 404


def test_quality_summary_endpoint_delta(client, auth, db_conn, users) -> None:  # type: ignore[no-untyped-def]
    # Delta để tất định dù DB có sẵn assistant message thật.
    before = client.get("/api/admin/logs/quality-summary", headers=auth("admin")).json()
    conv = create_conversation(users["teacher"].id, "t")
    add_message(conv.id, "assistant", "a", retrieval_mode="hybrid", citations=[{"c": 1}], confidence="cao")
    add_message(conv.id, "assistant", "b", retrieval_mode="hybrid", citations=[], confidence="thấp")
    add_message(conv.id, "assistant", "c", retrieval_mode="none", citations=[])  # không tính no_citation
    after = client.get("/api/admin/logs/quality-summary", headers=auth("admin")).json()
    assert after["total_assistant_messages"] - before["total_assistant_messages"] == 3
    assert after["retrieval_attempted_count"] - before["retrieval_attempted_count"] == 2
    assert after["no_citation_count"] - before["no_citation_count"] == 1
    assert after["low_confidence_count"] - before["low_confidence_count"] == 1


def test_logs_require_admin(client, auth) -> None:  # type: ignore[no-untyped-def]
    for path in ("/api/admin/logs/conversations", "/api/admin/logs/quality-summary"):
        r = client.get(path, headers=auth("teacher"))
        assert r.status_code == 403, path
