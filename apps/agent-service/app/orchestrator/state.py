"""LangGraph state cho answer flow. Xem `docs/plan/orchestrator-plan.md` §LangGraph state.

`warnings` tích lũy xuyên node (reducer add), `debug` merge dict. Còn lại overwrite.
`has_context` KHÔNG lưu field — là conditional edge đọc thẳng `retrieval.chunks`.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal

from typing_extensions import TypedDict

from app.schemas.ask import (
    AnswerConfidence,
    ChatMessage,
    Citation,
    PlanStep,
    RequestedMode,
    ResolvedFact,
    RouteDecision,
)
from app.schemas.retrieval import RetrievalMode, RetrievalResult
from app.schemas.visualization import VisualizationPayload


def _merge_debug(
    a: dict[str, object], b: dict[str, object]
) -> dict[str, object]:
    return {**a, **b}


class AgentState(TypedDict):
    question: str
    history: list[ChatMessage]
    # Snapshot system_config (RuntimeConfig.model_dump()) — ghi 1 lần đầu request ở runner
    # trước khi vào graph, các node chỉ ĐỌC (không I/O thêm). Xem app/core/runtime_config.py.
    runtime_config: dict[str, object]
    # id user backend (từ AskRequest.user_id) — gắn usage LLM vào đúng user cho cost dashboard.
    user_id: str | None
    # conversation_id + message_id (assistant) — gắn usage LLM về đúng hội thoại/message.
    conversation_id: str | None
    message_id: str | None
    standalone_query: str
    # Todo list do `plan` sinh + `planning.normalize_plan` kiểm; seed (`entities`) nằm TRONG
    # từng query của bước, không có field seed_mentions phẳng. Danh sách TĨNH: sinh một lần ở
    # `plan`, không bước nào được thêm/sửa bước lúc đang chạy (nếu sau này đổi, phải dựng lại
    # guard đếm lượt — `current_step` hiện là phanh duy nhất, xem plan §4.5).
    steps: list[PlanStep]
    # Index bước đang chạy (0-based). Điểm GHI DUY NHẤT là node `advance_step`; `retrieve` và
    # `resolve_step` chỉ ĐỌC. Một chỗ ghi = một chỗ test, không phải suy "ai tăng, tăng mấy lần".
    current_step: int
    # step_id -> mắt xích đã trích, dùng điền placeholder `<N>` của bước sau (execute-time).
    resolved: dict[int, str]
    # Cùng dữ liệu nhưng đủ ngữ cảnh để đưa vào prompt synthesize như fact CÓ NGUỒN.
    resolved_facts: list[ResolvedFact]
    # "" = todo list chạy hết bình thường; "unresolved" = dừng sớm (không truy hồi được gì ở
    # bước cần trích, hoặc trích ra rỗng/độ tin cậy thấp) -> trả lời bằng phần đang có.
    stop_reason: str
    # Mode từ request: "auto" = để `plan` chọn, giá trị cụ thể = user ép (bỏ qua plan).
    override_mode: RequestedMode
    # Mode THẬT dùng để truy hồi, `plan` giải xong mới có. Node retrieve dispatch theo field
    # này (không đọc override_mode nữa).
    selected_mode: RetrievalMode
    route: RouteDecision | None
    clarification_needed: bool
    clarification_question: str | None
    retrieval: RetrievalResult | None
    # "none" mặc định; node retrieve set = requested_mode (clarify/smalltalk/out_of_scope giữ none).
    retrieval_mode: Literal["traditional", "graph", "hybrid", "none"]
    answer: str | None
    confidence: AnswerConfidence | None
    # tăng sau MỖI synthesize; retry nếu < synthesize_max_attempts (guard chống loop).
    synthesize_attempt_count: int
    used_chunk_ids: list[str]
    citations: list[Citation]
    visualization: VisualizationPayload | None
    warnings: Annotated[list[str], operator.add]
    debug: Annotated[dict[str, object], _merge_debug]
