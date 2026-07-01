"""Schema cho Module 4 — Hội thoại & chất lượng (admin, read-only).

Chất lượng là SUY RA từ các cột đã lưu mỗi message (confidence/citations/
clarification_needed/warnings/retrieval_mode), không lưu cờ riêng. Xem
backend-additions-plan.md §3.1.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


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
