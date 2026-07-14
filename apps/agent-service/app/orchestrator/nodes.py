"""Node + conditional edge của answer graph. Xem `docs/plan/orchestrator-plan.md` §Nodes.

Mỗi node async nhận (state, config); lấy emitter từ config["configurable"]["emitter"].
LLM call dùng async client; retrieval/visualization (sync) bọc to_thread ở chỗ cần.
"""

from __future__ import annotations

import asyncio
from typing import Any

from langchain_core.runnables import RunnableConfig

from app.core.config import get_settings
from app.core.llm import get_async_openai_client
from app.core.runtime_config import RuntimeConfig
from app.core.usage_log import record_usage
from app.prompts import build_query as bq_prompt
from app.prompts import guardrails_input as gi_prompt
from app.prompts import synthesize as syn_prompt
from app.orchestrator.emitter import Emitter, NullEmitter
from app.orchestrator.errors import GuardrailsBlocked
from app.orchestrator.guardrails import check_input
from app.orchestrator.state import AgentState
from app.orchestrator.synthesis import (
    emit_text_as_batches,
    stream_static_text,
    stream_synthesis,
)
from app.schemas.ask import BuildQueryOutput, Citation, RouteDecision
from app.schemas.retrieval import RetrievedChunk
from app.tools.graph_rag.retriever import retrieve_graph
from app.tools.hybrid.retriever import retrieve_hybrid
from app.tools.prompts.prompt_store import get_active_prompt
from app.tools.reorder import reorder_for_context
from app.tools.traditional_rag.retriever import retrieve_traditional
from app.tools.visualization.builder import build_visualization as build_visualization_payload

HONEST_MESSAGE = (
    "Mình chưa tìm thấy đủ thông tin trong corpus hiện có để trả lời chắc chắn câu này. "
    "Bạn có thể hỏi cụ thể hơn về nhân vật, mốc thời gian hoặc sự kiện không?"
)

# Riêng mode=graph không ground được seed: gợi ý đổi mode (KHÔNG auto-fallback — quyết
# định user 2026-07-01). Các trường hợp honest khác giữ HONEST_MESSAGE.
GRAPH_EMPTY_MESSAGE = (
    "Mình chưa tìm thấy thực thể hoặc quan hệ phù hợp trong knowledge graph cho câu hỏi này "
    "ở chế độ Graph. Bạn thử lại bằng chế độ Traditional hoặc Hybrid để tìm theo nội dung "
    "tài liệu nhé."
)

# Độ dài trích đoạn kèm mỗi citation (hover ở frontend). Đủ dài để nhận ra đoạn nói gì,
# đủ ngắn để không phình payload SSE lẫn `messages.citations` JSONB. Full text lấy qua
# GET /api/chat/sources/{chunk_id} lúc user click — xem docs/plan/citation-viewer-plan.md.
CITATION_QUOTE_CHARS = 240


def _emitter(config: RunnableConfig | None) -> Emitter:
    cfg = (config or {}).get("configurable", {}) or {}
    emitter = cfg.get("emitter")
    return emitter if isinstance(emitter, Emitter) else NullEmitter()


def _orchestrator_model() -> str:
    settings = get_settings()
    return settings.orchestrator_llm_model or settings.llm_model


async def _record_usage_from_completion(
    completion: Any, task: str, state: AgentState
) -> None:
    """Ghi usage của 1 lệnh gọi LLM online (fire-and-forget). Completion không có `.usage`
    (vd mock cũ) -> bỏ qua êm. record_usage tự nuốt lỗi nên không làm fail flow. Gắn
    user_id/conversation_id/message_id từ state để quy usage về đúng user + hội thoại + message."""
    usage = getattr(completion, "usage", None)
    if usage is None:
        return
    await asyncio.to_thread(
        record_usage,
        task=task,
        model=_orchestrator_model(),
        prompt_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(usage, "completion_tokens", 0) or 0,
        total_tokens=getattr(usage, "total_tokens", 0) or 0,
        user_id=state.get("user_id"),
        conversation_id=state.get("conversation_id"),
        message_id=state.get("message_id"),
    )


# --- 0. guard_input (guardrails input layer — chạy TRƯỚC build_query) ---


async def guard_input(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Kiểm câu hỏi qua guardrails. allow -> đi tiếp build_query (ghi debug). block -> emit
    `token(safe_message)` + `blocked` rồi raise GuardrailsBlocked để DỪNG hẳn flow (không
    build_query/retrieve/synthesize, không emit done). check_input không bao giờ raise nên
    lỗi/timeout đã quy về allow/block theo fail_closed."""
    emitter = _emitter(config)
    decision = await check_input(
        state["question"],
        state["history"],
        user_id=state.get("user_id"),
        conversation_id=state.get("conversation_id"),
        message_id=state.get("message_id"),
    )
    if decision.action == "allow":
        return {"debug": {"guard_input": {"action": "allow"}}}

    safe = decision.safe_message or gi_prompt.DEFAULT_SAFE_MESSAGE
    # Nhả safe message dần từng cụm cho giống câu trả lời thường (rồi mới báo blocked).
    await stream_static_text(safe, emitter)
    await emitter.emit("blocked", {"stage": "input", "categories": decision.categories})
    raise GuardrailsBlocked(
        reason="input_guardrails", safe_message=safe, categories=decision.categories
    )


# --- 1. build_query (1 LLM call: rewrite + entity + route) ---


async def build_query(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    await emitter.emit("status", {"node": "build_query", "msg": "đang phân tích câu hỏi"})
    question = state["question"]
    history = state["history"]
    try:
        client = get_async_openai_client()
        completion = await client.chat.completions.parse(
            model=_orchestrator_model(),
            messages=[
                {
                    "role": "system",
                    "content": get_active_prompt("build_query", fallback=bq_prompt.SYSTEM_PROMPT),
                },
                {"role": "user", "content": bq_prompt.build_user_prompt(question, history)},
            ],
            response_format=BuildQueryOutput,
            temperature=0.0,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("build_query trả parsed None")
        await _record_usage_from_completion(completion, "build_query", state)
        return {
            "standalone_query": parsed.standalone_query.strip() or question,
            "seed_mentions": parsed.mentioned_entities,
            "route": parsed.route,
            "debug": {
                "build_query": {
                    "standalone_query": parsed.standalone_query,
                    "route": parsed.route,
                    "mentioned_entities": parsed.mentioned_entities,
                }
            },
        }
    except Exception as exc:  # noqa: BLE001 — fallback an toàn theo plan, không để LLM lỗi làm sập flow
        return {
            "standalone_query": question,
            "seed_mentions": [],
            "route": "needs_retrieval",
            "warnings": [f"build_query lỗi, fallback needs_retrieval: {type(exc).__name__}"],
        }


# --- 2. route_intent (conditional edge — chỉ đọc state.route, không LLM) ---

_ROUTE_TARGET: dict[RouteDecision, str] = {
    "needs_retrieval": "retrieve",
    "ambiguous": "clarify",
    "out_of_scope": "honest_answer",
    "smalltalk": "direct_response",
}


def route_intent(state: AgentState) -> str:
    route = state.get("route") or "needs_retrieval"
    return _ROUTE_TARGET.get(route, "retrieve")


# --- 3. retrieve (dispatch theo requested_mode; set retrieval_mode = mode đã chọn) ---


async def retrieve(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    mode = state["requested_mode"]
    cfg = RuntimeConfig.model_validate(state["runtime_config"])
    await emitter.emit("status", {"node": "retrieve", "msg": f"đang tìm tài liệu ({mode})"})
    # Retriever raise RetrievalBackendError khi backend chết -> propagate (API 503).
    # traditional KHÔNG dùng seed_mentions (đúng thiết kế); build_query vẫn chạy bình thường.
    # Mỗi mode chỉ nhận subset tham số tinh chỉnh của nó (Cấu hình hệ thống).
    if mode == "traditional":
        result = await retrieve_traditional(
            state["standalone_query"],
            top_k=cfg.rag_top_k,
            bm25_top_k=cfg.bm25_top_k,
            rerank_top_k=cfg.rerank_top_k,
        )
    elif mode == "graph":
        result = await retrieve_graph(
            state["standalone_query"],
            seed_mentions=state["seed_mentions"],
            graph_top_k=cfg.graph_top_k,
            graph_max_seed_entities=cfg.graph_max_seed_entities,
            graph_max_chunks_per_seed=cfg.graph_max_chunks_per_seed,
            graph_hub_source_count_threshold=cfg.graph_hub_source_count_threshold,
            graph_max_context_items=cfg.graph_max_context_items,
            graph_max_path_hops=cfg.graph_max_path_hops,
            graph_path_hit_weight=cfg.graph_path_hit_weight,
        )
    else:  # hybrid
        result = await retrieve_hybrid(
            state["standalone_query"],
            seed_mentions=state["seed_mentions"],
            rag_top_k=cfg.rag_top_k,
            graph_top_k=cfg.graph_top_k,
            hybrid_candidate_k=cfg.hybrid_candidate_k,
            hybrid_rrf_k=cfg.hybrid_rrf_k,
            rerank_top_k=cfg.rerank_top_k,
            bm25_top_k=cfg.bm25_top_k,
            graph_max_seed_entities=cfg.graph_max_seed_entities,
            graph_max_chunks_per_seed=cfg.graph_max_chunks_per_seed,
            graph_hub_source_count_threshold=cfg.graph_hub_source_count_threshold,
            graph_max_context_items=cfg.graph_max_context_items,
            graph_max_path_hops=cfg.graph_max_path_hops,
            graph_path_hit_weight=cfg.graph_path_hit_weight,
        )
    return {
        "retrieval": result,
        "retrieval_mode": mode,
        "warnings": result.warnings,
        "debug": {
            "retrieve": {
                "mode": mode,
                "chunks": len(result.chunks),
                "graph_context": len(result.graph_context),
            }
        },
    }


# --- 4. has_context (conditional edge — chỉ check có chunk không) ---


def has_context(state: AgentState) -> str:
    retrieval = state.get("retrieval")
    return "synthesize" if (retrieval and retrieval.chunks) else "honest_answer"


# --- 5. synthesize (stream structured output, answer field đầu) ---


async def synthesize(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    attempt = state.get("synthesize_attempt_count", 0)
    if attempt > 0:
        # Đây là lượt retry: answer lượt trước đã stream -> báo frontend clear.
        await emitter.emit("regenerating", {})
    await emitter.emit("status", {"node": "synthesize", "msg": "đang soạn câu trả lời"})
    settings = get_settings()
    cfg = RuntimeConfig.model_validate(state["runtime_config"])
    retrieval = state["retrieval"]
    assert retrieval is not None  # has_context đảm bảo có chunk trước khi vào đây
    # Document reordering (Phần F): xếp chunk điểm cao ra đầu/cuối prompt, chống "lost in the
    # middle". Thuần layout prompt — KHÔNG đổi retrieval.chunks lưu ở state (citation/viz giữ nguyên).
    chunks_for_prompt = reorder_for_context(retrieval.chunks)
    messages = [
        {
            "role": "system",
            "content": get_active_prompt("synthesize", fallback=syn_prompt.SYSTEM_PROMPT),
        },
        {
            "role": "user",
            "content": syn_prompt.build_user_prompt(
                state["standalone_query"],
                chunks_for_prompt,
                retrieval.graph_context,
                is_retry=attempt > 0,
            ),
        },
    ]
    user_id = state.get("user_id")
    conversation_id = state.get("conversation_id")
    message_id = state.get("message_id")

    async def _on_usage(prompt: int, completion: int, total: int) -> None:
        await asyncio.to_thread(
            record_usage,
            task="synthesize",
            model=_orchestrator_model(),
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            user_id=user_id,
            conversation_id=conversation_id,
            message_id=message_id,
        )

    result = await stream_synthesis(
        messages,
        emitter=emitter,
        model=_orchestrator_model(),
        batch_chars=settings.stream_batch_chars,
        temperature=cfg.llm_temperature,
        on_usage=_on_usage,
    )
    return {
        "answer": result.answer,
        "used_chunk_ids": result.used_chunk_ids,
        "confidence": result.confidence,
        "synthesize_attempt_count": attempt + 1,
    }


# --- 6. citation helpers (dùng inline trong build_visualization, không còn node riêng) ---


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _make_quote(text: str) -> str | None:
    """Trích đoạn ngắn LẤY TỪ chunk text (không nhờ LLM — xem orchestrator-plan §citation).

    Frontend hover citation là thấy ngay, không cần gọi API. Cắt ở ranh giới từ để không
    đứt giữa chữ tiếng Việt có dấu.
    """
    stripped = " ".join(text.split())
    if not stripped:
        return None
    if len(stripped) <= CITATION_QUOTE_CHARS:
        return stripped
    head = stripped[:CITATION_QUOTE_CHARS]
    cut = head.rfind(" ")
    return f"{head[:cut] if cut > 0 else head}…"


def _build_citation(chunk: RetrievedChunk) -> Citation:
    meta = chunk.metadata
    return Citation(
        chunk_id=chunk.chunk_id,
        source_file=_as_str(meta.get("source_file")),
        chunk_index=_as_int(meta.get("chunk_index")),
        start_line=_as_int(meta.get("start_line")),
        end_line=_as_int(meta.get("end_line")),
        heading_path=chunk.heading_path,
        quote=_make_quote(chunk.text),
    )


# --- 7. honest_answer ---


def _honest_message(state: AgentState) -> str:
    """Graph mode ground rỗng -> gợi ý đổi mode; còn lại -> message honest chung.

    Phân biệt chính xác: retrieval None = route bypass (out_of_scope); retrieval rỗng +
    mode graph = không ground được seed; retrieval có chunk nhưng citation fail = giữ chung.
    """
    retrieval = state.get("retrieval")
    if state.get("requested_mode") == "graph" and retrieval is not None and not retrieval.chunks:
        return GRAPH_EMPTY_MESSAGE
    return HONEST_MESSAGE


async def honest_answer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    if state.get("synthesize_attempt_count", 0) > 0:
        # synthesize đã stream answer (rồi bị loại) -> clear trước khi stream honest text.
        await emitter.emit("regenerating", {})
    await emitter.emit("status", {"node": "honest_answer", "msg": "chưa đủ dữ liệu"})
    settings = get_settings()
    message = _honest_message(state)
    await emit_text_as_batches(message, emitter, settings.stream_batch_chars)
    return {
        "answer": message,
        "confidence": "không đủ dữ liệu",
        "citations": [],
        "used_chunk_ids": [],
    }


# --- 7b. direct_response (smalltalk — không retrieve, không dùng message "không đủ corpus") ---


def _smalltalk_reply(question: str) -> str:
    q = question.lower()
    if any(w in q for w in ("cảm ơn", "cám ơn", "thank")):
        return "Không có gì! Bạn còn câu hỏi nào về lịch sử Việt Nam không?"
    return "Xin chào! Bạn muốn hỏi về sự kiện hoặc nhân vật lịch sử nào?"


async def direct_response(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    await emitter.emit("status", {"node": "direct_response", "msg": "trả lời xã giao"})
    settings = get_settings()
    text = _smalltalk_reply(state["question"])
    await emit_text_as_batches(text, emitter, settings.stream_batch_chars)
    return {"answer": text}


# --- 8. clarify (ambiguous — kết thúc ngay, trả clarification, KHÔNG retrieve) ---


def _clarification_question(question: str) -> str:
    q = question.lower()
    if "trận" in q:
        return "Bạn đang hỏi về trận đánh nào ạ?"
    if any(w in q for w in ("ông ấy", "bà ấy", "ông ta", "bà ta", "họ", "nhân vật")):
        return "Bạn đang hỏi về nhân vật nào ạ? (ví dụ: Hồ Chí Minh, Trương Định...)"
    return "Bạn có thể nói rõ hơn đang hỏi về nhân vật, sự kiện hay mốc thời gian nào không ạ?"


async def clarify(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    question = _clarification_question(state["question"])
    await emitter.emit("clarification", {"question": question})
    return {
        "clarification_needed": True,
        "clarification_question": question,
        "retrieval_mode": "none",
    }


# --- 9. build_visualization (build citation từ used_chunk_ids inline, không lọc/retry;
# viz fail không làm fail answer) ---


async def build_visualization(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    retrieval = state.get("retrieval")
    chunks_by_id = {c.chunk_id: c for c in (retrieval.chunks if retrieval else [])}
    citations = [
        _build_citation(chunks_by_id[cid])
        for cid in state.get("used_chunk_ids", [])
        if cid in chunks_by_id
    ]
    await emitter.emit(
        "citations", {"citations": [c.model_dump() for c in citations]}
    )
    used_ids = [c.chunk_id for c in citations]
    out: dict[str, Any] = {"citations": citations}
    viz = None
    try:
        viz = await asyncio.to_thread(build_visualization_payload, used_ids)
    except Exception as exc:  # noqa: BLE001 — viz lỗi không được làm fail answer (plan)
        out["warnings"] = [f"visualization lỗi: {type(exc).__name__}"]
    await emitter.emit(
        "visualization", {"visualization": viz.model_dump() if viz else None}
    )
    out["visualization"] = viz
    return out
