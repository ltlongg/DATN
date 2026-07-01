"""Request/response schema cho chat (conversations + messages + ask).

Lưu ý: `AskRequest` ở đây là contract FRONTEND -> BACKEND (không có `stream`: backend
luôn streaming). Contract BACKEND -> AGENT là `AgentAskRequest` trong services/agent_client.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.config import get_settings


class ConversationCreate(BaseModel):
    # title optional: rỗng/None -> backend đặt title tạm, suy từ câu hỏi đầu tiên ở /ask.
    title: str | None = Field(default=None, max_length=200)


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
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


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class AskRequest(BaseModel):
    # Backend luôn streaming. Frontend CHỌN mode truy hồi (traditional/graph/hybrid); mặc
    # định hybrid. max_length đồng bộ agent-service.
    question: str = Field(min_length=1, max_length=get_settings().ask_max_question_chars)
    mode: Literal["traditional", "graph", "hybrid"] = "hybrid"
    debug: bool = False
