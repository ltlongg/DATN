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
from app.core.usage_log import record_usage
from app.prompts import build_query as bq_prompt
from app.prompts import synthesize as syn_prompt
from app.orchestrator.emitter import Emitter, NullEmitter
from app.orchestrator.state import AgentState
from app.orchestrator.synthesis import emit_text_as_batches, stream_synthesis
from app.schemas.ask import BuildQueryOutput, Citation, RouteDecision
from app.schemas.retrieval import RetrievedChunk
from app.tools.hybrid.retriever import retrieve_hybrid
from app.tools.visualization.builder import build_visualization as build_visualization_payload

HONEST_MESSAGE = (
    "Mình chưa tìm thấy đủ thông tin trong corpus hiện có để trả lời chắc chắn câu này. "
    "Bạn có thể hỏi cụ thể hơn về nhân vật, mốc thời gian hoặc sự kiện không?"
)


def _emitter(config: RunnableConfig | None) -> Emitter:
    cfg = (config or {}).get("configurable", {}) or {}
    emitter = cfg.get("emitter")
    return emitter if isinstance(emitter, Emitter) else NullEmitter()


def _orchestrator_model() -> str:
    settings = get_settings()
    return settings.orchestrator_llm_model or settings.llm_model


async def _record_usage_from_completion(
    completion: Any, task: str, user_id: str | None
) -> None:
    """Ghi usage của 1 lệnh gọi LLM online (fire-and-forget). Completion không có `.usage`
    (vd mock cũ) -> bỏ qua êm. record_usage tự nuốt lỗi nên không làm fail flow."""
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
        user_id=user_id,
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
                {"role": "system", "content": bq_prompt.SYSTEM_PROMPT},
                {"role": "user", "content": bq_prompt.build_user_prompt(question, history)},
            ],
            response_format=BuildQueryOutput,
            temperature=0.0,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("build_query trả parsed None")
        await _record_usage_from_completion(
            completion, "build_query", state.get("user_id")
        )
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


# --- 3. retrieve (gọi thẳng hybrid, set retrieval_mode="hybrid") ---


async def retrieve(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    await emitter.emit("status", {"node": "retrieve", "msg": "đang tìm tài liệu"})
    # retrieve_hybrid raise RetrievalBackendError khi CẢ hai backend chết -> propagate (API 503).
    result = await retrieve_hybrid(
        state["standalone_query"], seed_mentions=state["seed_mentions"]
    )
    return {
        "retrieval": result,
        "retrieval_mode": "hybrid",
        "warnings": result.warnings,
        "debug": {
            "retrieve": {
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
    retrieval = state["retrieval"]
    assert retrieval is not None  # has_context đảm bảo có chunk trước khi vào đây
    messages = [
        {"role": "system", "content": syn_prompt.SYSTEM_PROMPT},
        {
            "role": "user",
            "content": syn_prompt.build_user_prompt(
                state["standalone_query"],
                retrieval.chunks,
                retrieval.graph_context,
                is_retry=attempt > 0,
            ),
        },
    ]
    user_id = state.get("user_id")

    async def _on_usage(prompt: int, completion: int, total: int) -> None:
        await asyncio.to_thread(
            record_usage,
            task="synthesize",
            model=_orchestrator_model(),
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            user_id=user_id,
        )

    result = await stream_synthesis(
        messages,
        emitter=emitter,
        model=_orchestrator_model(),
        batch_chars=settings.stream_batch_chars,
        on_usage=_on_usage,
    )
    return {
        "answer": result.answer,
        "used_chunk_ids": result.used_chunk_ids,
        "confidence": result.confidence,
        "synthesize_attempt_count": attempt + 1,
    }


# --- 6. validate_citations (server-side trust boundary, không LLM) ---


def _as_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _build_citation(chunk: RetrievedChunk) -> Citation:
    meta = chunk.metadata
    return Citation(
        chunk_id=chunk.chunk_id,
        source_file=_as_str(meta.get("source_file")),
        chunk_index=_as_int(meta.get("chunk_index")),
        start_line=_as_int(meta.get("start_line")),
        end_line=_as_int(meta.get("end_line")),
        heading_path=chunk.heading_path,
        quote=None,
    )


def validate_citations(state: AgentState) -> dict[str, Any]:
    retrieval = state["retrieval"]
    chunks_by_id = {c.chunk_id: c for c in (retrieval.chunks if retrieval else [])}
    seen: set[str] = set()
    citations: list[Citation] = []
    for cid in state.get("used_chunk_ids", []):
        # Drop id không nằm trong retrieval result; dedupe, giữ thứ tự LLM khai.
        if cid in chunks_by_id and cid not in seen:
            seen.add(cid)
            citations.append(_build_citation(chunks_by_id[cid]))
    return {"citations": citations}


def after_validate(state: AgentState) -> str:
    settings = get_settings()
    if state.get("confidence") == "không đủ dữ liệu":
        return "honest_answer"
    if state.get("citations"):
        return "build_visualization"
    # answer có nội dung nhưng không có citation hợp lệ.
    if state.get("synthesize_attempt_count", 0) < settings.synthesize_max_attempts:
        return "synthesize"
    return "honest_answer"


# --- 7. honest_answer ---


async def honest_answer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    if state.get("synthesize_attempt_count", 0) > 0:
        # synthesize đã stream answer (rồi bị loại) -> clear trước khi stream honest text.
        await emitter.emit("regenerating", {})
    await emitter.emit("status", {"node": "honest_answer", "msg": "chưa đủ dữ liệu"})
    settings = get_settings()
    await emit_text_as_batches(HONEST_MESSAGE, emitter, settings.stream_batch_chars)
    return {
        "answer": HONEST_MESSAGE,
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


# --- 9. build_visualization (online từ chunk đã citation; viz fail không làm fail answer) ---


async def build_visualization(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    citations = state.get("citations", [])
    # Đường này chỉ tới khi citations non-empty (after_validate đảm bảo).
    await emitter.emit(
        "citations", {"citations": [c.model_dump() for c in citations]}
    )
    used_ids = [c.chunk_id for c in citations]
    out: dict[str, Any] = {}
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
