"""Schema cho Module 4 — Hội thoại & chất lượng (admin, read-only).

Chất lượng là SUY RA từ các cột đã lưu mỗi message (confidence/citations/
clarification_needed/warnings/retrieval_mode), không lưu cờ riêng. Xem
backend-additions-plan.md §3.1.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ConversationLogItem(BaseModel):
    id: str
    title: str
    user_email: str
    user_name: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class ConversationLogResponse(BaseModel):
    items: list[ConversationLogItem]
    total: int
    limit: int
    offset: int


class MessageQuality(BaseModel):
    """Cờ chất lượng suy ra cho một message assistant (user message -> đều False)."""

    retrieval_attempted: bool
    no_citation: bool
    low_confidence: bool
    clarification: bool
    has_warning: bool


class MessageLogItem(BaseModel):
    id: str
    role: str
    content: str
    clarification_needed: bool
    citations: list[dict[str, Any]]
    visualization: dict[str, Any] | None
    retrieval_mode: str
    confidence: str | None
    warnings: list[Any]
    # Panel tiến trình đã lưu, KÈM `internals` của từng bước (số liệu thô trước đây nằm ở
    # DebugPanel realtime rồi bay mất). Đây là chỗ duy nhất admin xem lại được luồng xử lý
    # của một hội thoại đã đóng.
    steps: list[dict[str, Any]] = Field(default_factory=list)
    ttft_ms: int | None
    created_at: datetime
    quality: MessageQuality


class ConversationLogDetail(BaseModel):
    id: str
    title: str
    user_email: str
    user_name: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageLogItem]


class QualitySummary(BaseModel):
    # Mẫu số KHÁC NHAU theo field (xem quality_service): no_citation chia cho
    # retrieval_attempted_count, KHÔNG phải total_assistant_messages.
    total_assistant_messages: int
    retrieval_attempted_count: int
    no_citation_count: int
    low_confidence_count: int
    clarification_count: int
    warning_count: int
    # TTFT: mẫu số riêng = ttft_measured_count (message chưa đo được có ttft_ms NULL, không
    # tính vào trung bình). Cả hai None khi chưa message nào có số.
    ttft_measured_count: int
    avg_ttft_ms: float | None
    p95_ttft_ms: int | None


# --- Token theo hội thoại/message (song song chất lượng, xem admin-restructure-plan §Item 3) ---


class TokenOverall(BaseModel):
    """Tổng hợp token của các lượt gọi LLM ĐÃ gắn conversation_id trong khoảng ngày (card đầu
    tab). Row usage cũ conversation_id=NULL không tính ở đây — xem tab Chi phí cho tổng honest."""

    total_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    avg_tokens_per_call: float


class ConversationTokens(BaseModel):
    """Token cộng dồn của 1 hội thoại (cho cột token ở danh sách)."""

    conversation_id: str
    call_count: int
    total_tokens: int


class TokenSummary(BaseModel):
    overall: TokenOverall
    by_conversation: list[ConversationTokens]


class MessageTokenTaskRow(BaseModel):
    """1 dòng phân rã theo task trong 1 message. `model` ở mức task vì mỗi task có thể dùng
    model khác nhau (plan/synthesize vs guardrail_input)."""

    task: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class MessageTokens(BaseModel):
    message_id: str
    total_tokens: int
    rows: list[MessageTokenTaskRow]
