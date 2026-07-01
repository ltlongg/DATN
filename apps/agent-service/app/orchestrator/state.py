"""LangGraph state cho answer flow. Xem `docs/plan/orchestrator-plan.md` §LangGraph state.

`warnings` tích lũy xuyên node (reducer add), `debug` merge dict. Còn lại overwrite.
`has_context` KHÔNG lưu field — là conditional edge đọc thẳng `retrieval.chunks`.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal

from typing_extensions import TypedDict

from app.schemas.ask import AnswerConfidence, ChatMessage, Citation, RouteDecision
from app.schemas.retrieval import RetrievalResult
from app.schemas.visualization import VisualizationPayload


def _merge_debug(
    a: dict[str, object], b: dict[str, object]
) -> dict[str, object]:
    return {**a, **b}


class AgentState(TypedDict):
    question: str
    history: list[ChatMessage]
    # id user backend (từ AskRequest.user_id) — gắn usage LLM vào đúng user cho cost dashboard.
    user_id: str | None
    standalone_query: str
    seed_mentions: list[str]
    route: RouteDecision | None
    clarification_needed: bool
    clarification_question: str | None
    retrieval: RetrievalResult | None
    # "none" mặc định; chỉ node retrieve set "hybrid" (clarify/smalltalk/out_of_scope giữ none).
    retrieval_mode: Literal["hybrid", "none"]
    answer: str | None
    confidence: AnswerConfidence | None
    # tăng sau MỖI synthesize; retry nếu < synthesize_max_attempts (guard chống loop).
    synthesize_attempt_count: int
    used_chunk_ids: list[str]
    citations: list[Citation]
    visualization: VisualizationPayload | None
    warnings: Annotated[list[str], operator.add]
    debug: Annotated[dict[str, object], _merge_debug]
