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
    # Seed cho mode hybrid/graph, và là nguồn seed DUY NHẤT (không còn fallback token-match).
    # LUẬT: chỉ tên riêng xuất hiện NGUYÊN VĂN trong `standalone_query` — câu ĐÃ VIẾT LẠI, nên
    # tên model điền vào lúc thay đại từ là hợp lệ, còn tên nó tự nhớ ra thì không. Cưỡng chế
    # bằng code ở `orchestrator/planning.py`, không chỉ bằng prompt.
    entities: list[str] = Field(default_factory=list)


class PlanStep(BaseModel):
    """Một bước trong todo list, chạy theo thứ tự `id`.

    Câu thường = 1 bước không có `resolve` (không tốn LLM call nào giữa vòng). Câu multi-hop
    = 2 bước, bước đầu có `resolve` để trích mắt xích điền vào placeholder `<id>` của bước sau.
    """

    id: int
    label: str  # nhãn tiếng Việt ngắn, hiện lên panel tiến trình cho người dùng đọc
    queries: list[StepQuery]
    # Mô tả mắt xích cần trích từ chunk của CHÍNH bước này ("tên người kế nhiệm..."). Rỗng =
    # bước chỉ truy hồi. Bước CUỐI không được có (không ai tiêu thụ) — cưỡng chế ở planning.py.
    resolve: str = ""
    # id bước cung cấp mắt xích. Chỉ để kiểm tính hợp lệ + vẽ UI; thứ tự CHẠY là thứ tự `id`.
    depends_on: int | None = None


class PlanOutput(BaseModel):
    """Output 1 LLM call gộp rewrite + routing + phân rã truy vấn (tên cũ: BuildQueryOutput).

    `steps` rỗng là hợp lệ -> `planning.normalize_plan` dựng 1 bước mặc định từ
    `standalone_query`, tức hành vi y hệt trước khi có multi-query.

    THỨ TỰ FIELD CÓ Ý NGHĨA: Structured Outputs sinh JSON theo thứ tự property của schema, mà
    prompt v6 bắt trích `mentioned_entities` và chọn `selected_mode` bằng cách ĐỌC LẠI
    `standalone_query` — câu viết lại phải ra TRƯỚC thì model mới "thấy" nó ở hai bước sau.
    Đảo thứ tự là prompt nói dối model mà không có gì báo lỗi;
    `test_standalone_query_generated_before_entities_and_mode` khoá lại.
    """

    standalone_query: str
    mentioned_entities: list[str] = Field(default_factory=list)
    route: RouteDecision
    # Mode agent tự chọn cho CẢ câu hỏi. Bị bỏ qua khi request đã override mode cụ thể.
    selected_mode: AutoSelectableMode = "hybrid"
    steps: list[PlanStep] = Field(default_factory=list)


class StepResolveOutput(BaseModel):
    """Output node `resolve_step`: mắt xích trích được từ context của bước vừa chạy.

    Ngắn có chủ đích — chính vì output chỉ là một cái tên nên đưa được TOÀN VĂN chunk vào
    prompt (khác hẳn `reflect` đã bỏ, vốn chỉ đọc 240 ký tự đầu mỗi chunk rồi phán "đủ chưa").

    `confidence`/`source_chunk_ids` là bắt buộc chứ không trang trí: đáp án trung gian đi vào
    prompt synthesize như một fact CÓ NGUỒN, và `thấp` thì dừng list thay vì tra tiếp bằng
    một cái tên đoán mò (§0.2 mục 6 — sai lan truyền).
    """

    value: str = ""  # "" = không thấy trong context
    confidence: AnswerConfidence = "thấp"
    source_chunk_ids: list[str] = Field(default_factory=list)


class ResolvedFact(BaseModel):
    """Mắt xích đã trích ở một bước, mang sang `synthesize` như một fact CÓ NGUỒN.

    Không phải output LLM (đó là `StepResolveOutput`) mà là bản ghi state: thêm `step_id` +
    `label` để panel tiến trình và prompt gọi tên được bước đã sinh ra nó.
    """

    step_id: int
    label: str
    value: str
    confidence: AnswerConfidence
    source_chunk_ids: list[str] = Field(default_factory=list)


class SynthesizedAnswer(BaseModel):
    """Output synthesize. `answer` PHẢI là field đầu -> token stream ra trước, còn
    `used_chunk_ids`/`confidence` về ở cuối để validate sau khi answer đã stream."""

    answer: str
    used_chunk_ids: list[str] = Field(default_factory=list)
    confidence: AnswerConfidence
