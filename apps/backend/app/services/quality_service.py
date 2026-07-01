"""Logic thuần (không I/O) suy ra chất lượng từ các cột đã lưu mỗi assistant message.

Tách thuần để unit-test không cần DB (cùng idiom conversation_service.py::derive_title).
Điểm mấu chốt (backend-additions-plan.md §3.1): **mẫu số khác nhau theo field**.
`clarify()`/`direct_response`/route `out_of_scope` KHÔNG qua retrieve() nên
`retrieval_mode` giữ `"none"` và `citations=[]` là BÌNH THƯỜNG — không tính vào
`no_citation`. Chỉ message ĐÃ thử retrieval (`retrieval_mode != "none"`) mà vẫn rỗng
citation mới là tín hiệu đáng chú ý.
"""

from __future__ import annotations

from typing import Any

from app.schemas.logs import MessageQuality, QualitySummary

# Đồng bộ AnswerConfidence của agent-service: "thấp"/"không đủ dữ liệu" = chất lượng thấp.
_LOW_CONFIDENCE = {"thấp", "không đủ dữ liệu"}


def message_quality_flags(row: dict[str, Any]) -> MessageQuality:
    """Cờ chất lượng cho MỘT message. `no_citation` chỉ True khi đã thử retrieval mà rỗng
    citation (message không retrieval vốn dĩ không có citation -> không đánh dấu)."""
    attempted = (row.get("retrieval_mode") or "none") != "none"
    citations = row.get("citations") or []
    return MessageQuality(
        retrieval_attempted=attempted,
        no_citation=attempted and not citations,
        low_confidence=row.get("confidence") in _LOW_CONFIDENCE,
        clarification=bool(row.get("clarification_needed")),
        has_warning=bool(row.get("warnings")),
    )


def compute_quality_summary(rows: list[dict[str, Any]]) -> QualitySummary:
    """Tổng hợp đếm trên các assistant message. Mẫu số khác nhau theo field (xem docstring)."""
    total = len(rows)
    retrieval_attempted = 0
    no_citation = 0
    low_confidence = 0
    clarification = 0
    warning = 0
    for row in rows:
        flags = message_quality_flags(row)
        if flags.retrieval_attempted:
            retrieval_attempted += 1
            if flags.no_citation:
                no_citation += 1
        if flags.low_confidence:
            low_confidence += 1
        if flags.clarification:
            clarification += 1
        if flags.has_warning:
            warning += 1
    return QualitySummary(
        total_assistant_messages=total,
        retrieval_attempted_count=retrieval_attempted,
        no_citation_count=no_citation,
        low_confidence_count=low_confidence,
        clarification_count=clarification,
        warning_count=warning,
    )
