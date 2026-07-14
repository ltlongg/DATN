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


class ConversationUpdate(BaseModel):
    # Đổi tên conversation; title bắt buộc, không rỗng sau khi trim (kiểm ở endpoint).
    title: str = Field(min_length=1, max_length=200)


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
    # TTFT (ms): nhận /ask -> token đầu tiên. None với message user / message lưu trước khi
    # có tính năng này.
    ttft_ms: int | None
    created_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut]


class AskRequest(BaseModel):
    # Backend luôn streaming. Frontend CHỌN mode truy hồi (traditional/graph/hybrid); mặc
    # định hybrid. max_length đồng bộ agent-service.
    question: str = Field(min_length=1, max_length=get_settings().ask_max_question_chars)
    mode: Literal["traditional", "graph", "hybrid"] = "hybrid"
    debug: bool = False


class SourceDetail(BaseModel):
    """Toàn văn 1 chunk cho modal "xem nguồn" khi user nhấn citation.

    Chỉ đúng những gì modal hiện: text + tiêu đề mục + số dòng (số dòng CHỈ có nghĩa ở đây,
    danh sách nguồn không in — xem docs/plan/citation-viewer-plan.md §3). KHÔNG trả
    `source_file`/`chunk_index` (UI không bao giờ hiện tên file) lẫn `referencing_events`
    (thông tin soi kho của KB Inspector, người dùng không cần).
    """

    chunk_id: str
    text: str
    heading_path: list[str]
    start_line: int | None
    end_line: int | None
