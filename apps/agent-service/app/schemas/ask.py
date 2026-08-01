"""Contract cho /ask API và orchestrator answer flow.

Định nghĩa MỘT chỗ cho `RouteDecision` (dùng lại ở `PlanOutput`, `AgentState`),
request/response của `/ask`, và hai schema structured-output của LLM (`PlanOutput`,
`SynthesizedAnswer`). Xem `docs/plan/orchestrator-plan.md` +
`docs/plan/agentic-retrieval-loop-plan.md`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.visualization import VisualizationPayload

# Single source of truth — dùng lại ở PlanOutput.route và AgentState["route"].
RouteDecision = Literal["needs_retrieval", "ambiguous", "out_of_scope", "smalltalk"]

# Thang confidence của câu trả lời (đồng bộ AliasVerdict + timeline).
AnswerConfidence = Literal["cao", "vừa", "thấp", "không đủ dữ liệu"]

# Mode ở TẦNG REQUEST: thêm "auto" so với `RetrievalMode` nội bộ. CỐ Ý không nhét "auto" vào
# `RetrievalMode` — "auto" là ý định của người gọi, không phải một cách truy hồi; nó luôn được
# giải thành 1 trong 3 giá trị thật TRƯỚC khi tới node retrieve.
RequestedMode = Literal["auto", "traditional", "graph", "hybrid"]

# Mode node `plan` được phép tự chọn. KHÔNG có "graph": mode graph đứng riêng đã bỏ khỏi
# lựa chọn mặc định (graph vẫn sống bên trong hybrid), chỉ còn là override thủ công.
AutoSelectableMode = Literal["traditional", "hybrid"]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    # "auto" = node `plan` tự chọn mode (mặc định). Giá trị cụ thể = user OVERRIDE, bỏ qua
    # lựa chọn của plan. `graph` chỉ còn dùng cho demo/đánh giá, không hiện ở UI mặc định.
    mode: RequestedMode = "auto"
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


class StepQuery(BaseModel):
    """Một truy vấn chạy độc lập. Nhiều StepQuery trong cùng bước -> chạy SONG SONG."""

    query: str
    # Seed cho mode hybrid. LUẬT: chỉ tên riêng xuất hiện NGUYÊN VĂN trong câu hỏi hiện tại
    # (không lấy từ history, không lấy từ kiến thức nội tại của model). Cưỡng chế bằng code ở
    # `orchestrator/planning.py`, không chỉ bằng prompt.
    entities: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    """Một bước trong todo list. B1 chỉ chạy đúng 1 bước; nhiều bước là bậc B4."""

    id: int
    label: str  # nhãn tiếng Việt ngắn, hiện lên DebugPanel (và panel tiến trình ở B3)
    queries: list[StepQuery]


class PlanOutput(BaseModel):
    """Output 1 LLM call gộp rewrite + routing + phân rã truy vấn (tên cũ: BuildQueryOutput).

    `steps` rỗng là hợp lệ -> `planning.normalize_plan` dựng 1 bước mặc định từ
    `standalone_query`, tức hành vi y hệt trước khi có multi-query.
    """

    standalone_query: str
    mentioned_entities: list[str] = Field(default_factory=list)
    route: RouteDecision
    # Mode agent tự chọn cho CẢ câu hỏi. Bị bỏ qua khi request đã override mode cụ thể.
    selected_mode: AutoSelectableMode = "hybrid"
    steps: list[PlanStep] = Field(default_factory=list)


class SynthesizedAnswer(BaseModel):
    """Output synthesize. `answer` PHẢI là field đầu -> token stream ra trước, còn
    `used_chunk_ids`/`confidence` về ở cuối để validate sau khi answer đã stream."""

    answer: str
    used_chunk_ids: list[str] = Field(default_factory=list)
    confidence: AnswerConfidence
