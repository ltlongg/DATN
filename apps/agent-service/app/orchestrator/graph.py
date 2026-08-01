"""Wiring answer graph. Xem `docs/plan/orchestrator-plan.md` §Graph flow.

START -> guard_input -> plan -> (route_intent) -> retrieve|clarify|honest_answer|direct_response
retrieve -> (after_retrieve) -> resolve_step|advance_step|synthesize|honest_answer
resolve_step -> (after_resolve) -> advance_step|synthesize|honest_answer
advance_step -> (after_advance) -> retrieve|synthesize|honest_answer
synthesize -> validate_citations -> (after_validate) -> build_visualization|synthesize|honest_answer
clarify|direct_response|honest_answer|build_visualization -> END

guard_input (guardrails input layer): allow -> plan; block -> raise GuardrailsBlocked
(dừng flow, không có edge ra; runner streaming đã emit token+blocked, không emit done).

HAI vòng lặp, mỗi vòng một cái đáy khác nhau:

1. `advance_step -> retrieve` (B4, todo list nhiều bước). Đáy là `current_step` — tăng đơn
   điệu, ghi ở ĐÚNG một chỗ (`advance_step`), và `len(steps)` cố định vì todo list sinh một
   lần ở `plan` rồi không đổi. Cộng thêm cap cứng `retrieval_max_steps` lúc validate plan.
2. `validate_citations -> synthesize` (B5, soạn lại khi 0 liên kết nguồn hợp lệ). Đáy là
   `synthesize_attempt_count < synthesize_max_attempts` đọc trong `after_validate`;
   `synthesize` tăng counter mỗi lượt.
"""

from __future__ import annotations

from functools import lru_cache

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from app.orchestrator import nodes
from app.orchestrator.state import AgentState


@lru_cache(maxsize=1)
def get_graph() -> CompiledStateGraph:
    """Compile graph một lần (không checkpointer — flow stateless, xem plan §3)."""
    builder = StateGraph(AgentState)

    builder.add_node("guard_input", nodes.guard_input)
    builder.add_node("plan", nodes.plan)
    builder.add_node("retrieve", nodes.retrieve)
    builder.add_node("resolve_step", nodes.resolve_step)
    builder.add_node("advance_step", nodes.advance_step)
    builder.add_node("synthesize", nodes.synthesize)
    builder.add_node("validate_citations", nodes.validate_citations)
    builder.add_node("honest_answer", nodes.honest_answer)
    builder.add_node("direct_response", nodes.direct_response)
    builder.add_node("clarify", nodes.clarify)
    builder.add_node("build_visualization", nodes.build_visualization)

    # guard_input chạy đầu tiên; block -> raise GuardrailsBlocked (dừng, không edge). allow ->
    # chảy thẳng sang plan như luồng cũ.
    builder.add_edge(START, "guard_input")
    builder.add_edge("guard_input", "plan")
    builder.add_conditional_edges(
        "plan",
        nodes.route_intent,
        ["retrieve", "clarify", "honest_answer", "direct_response"],
    )
    builder.add_conditional_edges(
        "retrieve",
        nodes.after_retrieve,
        ["resolve_step", "advance_step", "synthesize", "honest_answer"],
    )
    builder.add_conditional_edges(
        "resolve_step",
        nodes.after_resolve,
        ["advance_step", "synthesize", "honest_answer"],
    )
    builder.add_conditional_edges(
        "advance_step", nodes.after_advance, ["retrieve", "synthesize", "honest_answer"]
    )
    builder.add_edge("synthesize", "validate_citations")
    builder.add_conditional_edges(
        "validate_citations",
        nodes.after_validate,
        ["build_visualization", "synthesize", "honest_answer"],
    )
    builder.add_edge("clarify", END)
    builder.add_edge("direct_response", END)
    builder.add_edge("honest_answer", END)
    builder.add_edge("build_visualization", END)

    return builder.compile()
