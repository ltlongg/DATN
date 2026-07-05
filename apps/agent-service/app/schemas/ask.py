"""Contract cho /ask API và orchestrator answer flow.

Định nghĩa MỘT chỗ cho `RouteDecision` (dùng lại ở `BuildQueryOutput`, `AgentState`),
request/response của `/ask`, và hai schema structured-output của LLM (`BuildQueryOutput`,
`SynthesizedAnswer`). Xem `docs/plan/orchestrator-plan.md`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.retrieval import RetrievalMode
from app.schemas.visualization import VisualizationPayload

# Single source of truth — dùng lại ở BuildQueryOutput.route và AgentState["route"].
RouteDecision = Literal["needs_retrieval", "ambiguous", "out_of_scope", "smalltalk"]

# Thang confidence của câu trả lời (đồng bộ AliasVerdict + timeline).
AnswerConfidence = Literal["cao", "vừa", "thấp", "không đủ dữ liệu"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    # User CHỌN TAY 1 trong 3 mode (không để LLM đoán). Mặc định hybrid (hành vi cũ).
    mode: RetrievalMode = "hybrid"
    stream: bool = True  # True -> SSE; False -> gom event trả 1 AskResponse JSON
    debug: bool = False
    # id user backend (đã decode từ JWT) — để gắn usage vào đúng user. KHÔNG phải field FE
    # gửi trực tiếp; backend tự điền.
    user_id: str | None = None
    # conversation_id + message_id (assistant) backend tự điền để quy usage LLM về đúng
    # hội thoại/message (token per hội thoại). Giống user_id: FE không gửi trực tiếp.
    conversation_id: str | None = None
    message_id: str | None = None


class Citation(BaseModel):
    chunk_id: str
    source_file: str | None = None
    chunk_index: int | None = None
    start_line: int | None = None
    end_line: int | None = None
    heading_path: list[str] = Field(default_factory=list)
    quote: str | None = None


class AskResponse(BaseModel):
    # clarification_needed=True -> answer=None, các field còn lại rỗng. Frontend hiển thị
    # clarification_question -> user trả lời -> request mới kèm history.
    clarification_needed: bool = False
    clarification_question: str | None = None
    answer: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    # "none" khi không retrieve (clarify/smalltalk/out_of_scope); else = mode đã chọn.
    retrieval_mode: Literal["traditional", "graph", "hybrid", "none"] = "none"
    confidence: AnswerConfidence | None = None
    visualization: VisualizationPayload | None = None
    warnings: list[str] = Field(default_factory=list)
    debug: dict[str, object] | None = None


# --- LLM structured outputs ---


class BuildQueryOutput(BaseModel):
    """Output 1 LLM call gộp rewrite + entity extraction + routing."""

    standalone_query: str
    mentioned_entities: list[str] = Field(default_factory=list)
    route: RouteDecision


class SynthesizedAnswer(BaseModel):
    """Output synthesize. `answer` PHẢI là field đầu -> token stream ra trước, còn
    `used_chunk_ids`/`confidence` về ở cuối để validate sau khi answer đã stream."""

    answer: str
    used_chunk_ids: list[str] = Field(default_factory=list)
    confidence: AnswerConfidence
