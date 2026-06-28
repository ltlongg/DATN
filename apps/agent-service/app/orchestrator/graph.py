"""Wiring answer graph. Xem `docs/plan/orchestrator-plan.md` §Graph flow.

START -> build_query -> (route_intent) -> retrieve|clarify|honest_answer|direct_response
retrieve -> (has_context) -> synthesize|honest_answer
synthesize -> validate_citations -> (after_validate) -> build_visualization|synthesize(retry)|honest_answer
clarify|direct_response|honest_answer|build_visualization -> END
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

    builder.add_node("build_query", nodes.build_query)
    builder.add_node("retrieve", nodes.retrieve)
    builder.add_node("synthesize", nodes.synthesize)
    builder.add_node("validate_citations", nodes.validate_citations)
    builder.add_node("honest_answer", nodes.honest_answer)
    builder.add_node("direct_response", nodes.direct_response)
    builder.add_node("clarify", nodes.clarify)
    builder.add_node("build_visualization", nodes.build_visualization)

    builder.add_edge(START, "build_query")
    builder.add_conditional_edges(
        "build_query",
        nodes.route_intent,
        ["retrieve", "clarify", "honest_answer", "direct_response"],
    )
    builder.add_conditional_edges(
        "retrieve", nodes.has_context, ["synthesize", "honest_answer"]
    )
    builder.add_edge("synthesize", "validate_citations")
    builder.add_conditional_edges(
        "validate_citations",
        nodes.after_validate,
        ["synthesize", "build_visualization", "honest_answer"],
    )
    builder.add_edge("clarify", END)
    builder.add_edge("direct_response", END)
    builder.add_edge("honest_answer", END)
    builder.add_edge("build_visualization", END)

    return builder.compile()
