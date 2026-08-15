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

def _ttft_stats(rows: list[dict[str, Any]]) -> tuple[int, float | None, int | None]:
    """(số message đo được, TTFT trung bình ms, p95 ms). Bỏ qua row ttft_ms NULL — message
    lưu trước khi có tính năng này hoặc stream hỏng trước token đầu. p95 lấy theo phương pháp
    nearest-rank (không nội suy): phần tử thứ ceil(0.95 * n) của dãy đã sắp."""
    values = sorted(
        int(r["ttft_ms"]) for r in rows if isinstance(r.get("ttft_ms"), int)
    )
    if not values:
        return 0, None, None
    n = len(values)
    rank = -(-95 * n // 100)  # ceil(0.95 * n), tối thiểu 1
    return n, sum(values) / n, values[rank - 1]

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
    ttft_count, avg_ttft, p95_ttft = _ttft_stats(rows)
    return QualitySummary(
        total_assistant_messages=total,
        retrieval_attempted_count=retrieval_attempted,
        no_citation_count=no_citation,
        low_confidence_count=low_confidence,
        clarification_count=clarification,
        warning_count=warning,
        ttft_measured_count=ttft_count,
        avg_ttft_ms=avg_ttft,
        p95_ttft_ms=p95_ttft,
    )
