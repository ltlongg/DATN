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
from app.prompts import guardrails_input as gi_prompt
from app.prompts import plan as plan_prompt
from app.prompts import synthesize as syn_prompt
from app.orchestrator.emitter import Emitter, NullEmitter
from app.orchestrator.errors import GuardrailsBlocked
from app.orchestrator.fusion import answer_context_chunks, fuse_query_results
from app.orchestrator.guardrails import check_input
from app.orchestrator.planning import DEFAULT_STEP_LABEL, normalize_plan
from app.orchestrator import progress
from app.orchestrator.state import AgentState
from app.orchestrator.synthesis import (
    emit_text_as_batches,
    stream_static_text,
    stream_synthesis,
)
from app.schemas.ask import (
    AutoSelectableMode,
    Citation,
    PlanOutput,
    PlanStep,
    RequestedMode,
    RouteDecision,
    StepQuery,
)
from app.schemas.retrieval import RetrievalMode, RetrievalResult, RetrievedChunk
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

# Bậc B1 chạy ĐÚNG một bước todo. CỐ Ý là hằng số chứ không phải knob config: knob
# `retrieval_max_steps` chỉ có nghĩa khi vòng lặp nhiều bước tồn tại (bậc B4) — thêm sớm thì
# chỉnh nó không đổi được gì, mà một knob chỉnh không ăn thua còn tệ hơn không có knob.
MAX_STEPS = 1


def _emitter(config: RunnableConfig | None) -> Emitter:
    cfg = (config or {}).get("configurable", {}) or {}
    emitter = cfg.get("emitter")
    return emitter if isinstance(emitter, Emitter) else NullEmitter()


async def _emit_step(
    emitter: Emitter,
    step_id: str,
    state: progress.StepState,
    detail: str | None = None,
    internals: list[progress.InternalRow] | None = None,
) -> None:
    """Cập nhật MỘT dòng của panel tiến trình (§7.3.1). Dòng phải đã được khai báo trong
    event `steps` trước đó — frontend bỏ qua id lạ để không mọc dòng ma.

    `internals` = tầng 2 (số liệu thô, thay DebugPanel cũ). Gửi kèm ngay tại bước sinh ra nó;
    backend mới là chỗ quyết định có forward xuống người dùng hay không — xem progress.py.
    """
    data: dict[str, object] = {"id": step_id, "state": state}
    if detail is not None:
        data["detail"] = detail
    if internals:
        data["internals"] = internals
    await emitter.emit("step", data)


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
    # Panel tiến trình: chặn ở cửa thì flow dừng tại đây, `plan` không bao giờ chạy. Không
    # nói gì thì dòng "Phân tích câu hỏi" mà frontend dựng sẵn bị hạ về `partial` trống
    # trơn — nhìn như hệ thống hỏng, chứ không phải như câu hỏi bị từ chối.
    await emitter.emit(
        "steps", {"steps": [{"id": progress.PLAN_STEP_ID, "label": progress.PLAN_STEP_LABEL,
                             "kind": "system"}]}
    )
    await _emit_step(
        emitter, progress.PLAN_STEP_ID, "partial", "Bộ lọc an toàn đã chặn câu hỏi"
    )
    # Nhả safe message dần từng cụm cho giống câu trả lời thường (rồi mới báo blocked).
    await stream_static_text(safe, emitter)
    await emitter.emit("blocked", {"stage": "input", "categories": decision.categories})
    raise GuardrailsBlocked(
        reason="input_guardrails", safe_message=safe, categories=decision.categories
    )


# --- 1. plan (1 LLM call: rewrite + route + phân rã truy vấn) ---


def _fallback_steps(question: str) -> list[PlanStep]:
    """Không có todo list dùng được -> 1 bước 1 query từ chính câu hỏi (hành vi tiền-B1)."""
    return [
        PlanStep(id=1, label=DEFAULT_STEP_LABEL, queries=[StepQuery(query=question)])
    ]


def _resolve_mode(override: RequestedMode, chosen: AutoSelectableMode) -> RetrievalMode:
    """Override của user THẮNG lựa chọn của agent; chỉ "auto" mới nhường quyền cho agent."""
    return chosen if override == "auto" else override


async def plan(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    await emitter.emit("status", {"node": "plan", "msg": "đang phân tích câu hỏi"})
    question = state["question"]
    history = state["history"]
    override = state["override_mode"]
    settings = get_settings()
    try:
        client = get_async_openai_client()
        completion = await client.chat.completions.parse(
            model=_orchestrator_model(),
            messages=[
                {
                    "role": "system",
                    # Key managed prompt GIỮ "build_query" dù node/file đã đổi tên sang `plan`
                    # — đổi key là phải reseed DB + mất lịch sử version. Xem prompts/plan.py.
                    "content": get_active_prompt(
                        "build_query", fallback=plan_prompt.SYSTEM_PROMPT
                    ),
                },
                {"role": "user", "content": plan_prompt.build_user_prompt(question, history)},
            ],
            response_format=PlanOutput,
            temperature=0.0,
        )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("plan trả parsed None")
        await _record_usage_from_completion(completion, "plan", state)
        standalone, steps, warnings = normalize_plan(
            parsed,
            question,
            max_steps=MAX_STEPS,
            max_queries_per_step=settings.max_queries_per_step,
        )
        selected = _resolve_mode(override, parsed.selected_mode)
        mode_source = "override" if override != "auto" else "agent"
        # Panel tiến trình: danh sách dòng chỉ dựng được SAU khi biết route + số bước
        # (§7.3 mục 3 — không giả vờ biết trước kịch bản). Dòng `plan` đã do frontend
        # render sẵn ở trạng thái running lúc mở stream, đây là lúc chốt nó.
        await emitter.emit("steps", {"steps": progress.build_step_list(parsed.route, steps)})
        await _emit_step(
            emitter,
            progress.PLAN_STEP_ID,
            "done",
            progress.plan_detail(parsed.route, steps),
            progress.plan_internals(
                standalone_query=standalone,
                route=parsed.route,
                selected_mode=selected,
                mode_source=mode_source,
            ),
        )
        return {
            "standalone_query": standalone,
            "steps": steps,
            "selected_mode": selected,
            "route": parsed.route,
            "warnings": warnings,
            "debug": {
                "plan": {
                    "standalone_query": standalone,
                    "route": parsed.route,
                    "selected_mode": selected,
                    "mode_source": mode_source,
                    "steps": [s.model_dump() for s in steps],
                }
            },
        }
    except Exception as exc:  # noqa: BLE001 — fallback an toàn theo plan, không để LLM lỗi làm sập flow
        fallback = _fallback_steps(question)
        fallback_mode = _resolve_mode(override, "hybrid")
        # `partial`, KHÔNG phải `done`: phân tích đã hỏng và ta đang chạy bằng nguyên câu
        # hỏi. Cho tick xanh ở đây là nói dối người dùng về việc hệ thống vừa làm.
        await emitter.emit(
            "steps", {"steps": progress.build_step_list("needs_retrieval", fallback)}
        )
        await _emit_step(
            emitter,
            progress.PLAN_STEP_ID,
            "partial",
            "Không phân tích được · tìm bằng nguyên câu hỏi",
            # Tên exception: dòng phụ nói với người dùng là "không phân tích được", còn admin
            # cần biết hỏng ở đâu. Trước đây nó chỉ lọt ra qua `warnings` (hiện cho MỌI người).
            [
                {"label": "Lỗi", "value": type(exc).__name__},
                {"label": "Cách truy hồi", "value": f"{fallback_mode} (fallback)"},
            ],
        )
        return {
            "standalone_query": question,
            "steps": fallback,
            # LLM chết thì không biết mode nào hợp; hybrid là siêu tập (dense + BM25 + graph)
            # nên an toàn nhất. Override của user vẫn phải được tôn trọng.
            "selected_mode": fallback_mode,
            "route": "needs_retrieval",
            "warnings": [f"plan lỗi, fallback needs_retrieval: {type(exc).__name__}"],
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


# --- 3. retrieve (fan-out mọi query của bước hiện tại; set retrieval_mode = mode đã chọn) ---


async def _retrieve_one(
    item: StepQuery, mode: RetrievalMode, cfg: RuntimeConfig
) -> RetrievalResult:
    """Một lượt truy hồi cho MỘT query. Mỗi mode chỉ nhận subset knob của nó.

    `seed_mentions` truyền None khi rỗng chứ KHÔNG truyền []: `match_seed_entities` phân biệt
    hai thứ đó — None thì token-match từ chuỗi query (fallback tất định), còn [] là "có danh
    sách seed và nó rỗng" nên graph tắt hẳn. Guard §2.1 lọc sạch entity là chuyện thường gặp,
    không được biến nó thành tắt graph.
    """
    seeds = item.entities or None
    if mode == "traditional":
        # traditional CỐ Ý không dùng seed_mentions (thiết kế: dense + BM25 thuần).
        return await retrieve_traditional(
            item.query,
            top_k=cfg.rag_top_k,
            bm25_top_k=cfg.bm25_top_k,
            rerank_top_k=cfg.rerank_top_k,
        )
    if mode == "graph":
        return await retrieve_graph(
            item.query,
            seed_mentions=seeds,
            graph_top_k=cfg.graph_top_k,
            graph_max_seed_entities=cfg.graph_max_seed_entities,
            graph_max_chunks_per_seed=cfg.graph_max_chunks_per_seed,
            graph_hub_source_count_threshold=cfg.graph_hub_source_count_threshold,
            graph_max_context_items=cfg.graph_max_context_items,
            graph_max_path_hops=cfg.graph_max_path_hops,
            graph_path_hit_weight=cfg.graph_path_hit_weight,
        )
    return await retrieve_hybrid(
        item.query,
        seed_mentions=seeds,
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


async def retrieve(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    mode = state["selected_mode"]
    cfg = RuntimeConfig.model_validate(state["runtime_config"])
    settings = get_settings()
    step = state["steps"][0]  # B1: `plan` bảo đảm đúng 1 bước
    step_id = progress.todo_step_id(step.id)
    await emitter.emit("status", {"node": "retrieve", "msg": f"đang tìm tài liệu ({mode})"})
    await _emit_step(emitter, step_id, "running")
    # Retriever raise RetrievalBackendError khi backend chết -> propagate (API 503). Dòng
    # này ở lại trạng thái running; frontend hạ mọi dòng running xuống partial khi stream
    # đóng mà chưa có kết (§7.3.1 mục 5) nên không cần bắt lỗi riêng ở đây.
    results = await asyncio.gather(
        *[_retrieve_one(item, mode, cfg) for item in step.queries]
    )
    chunks, graph_context = fuse_query_results(
        list(results), rrf_k=cfg.hybrid_rrf_k, final_k=settings.multiquery_final_k
    )
    merged = RetrievalResult(
        mode=mode,
        query=state["standalone_query"],
        chunks=chunks,
        graph_context=graph_context,
        warnings=[w for r in results for w in r.warnings],
    )
    # Một list dùng cho CẢ hai đường ra (event `step` tầng 2 và `debug` của /ask non-stream)
    # — dựng hai lần là mở đường cho hai con số lệch nhau.
    query_rows = [
        {"query": item.query, "entities": item.entities, "chunks": len(r.chunks)}
        for item, r in zip(step.queries, results)
    ]
    await _emit_step(
        emitter,
        step_id,
        progress.retrieve_state(len(chunks)),
        progress.retrieve_detail(
            mode, query_count=len(step.queries), chunk_count=len(chunks)
        ),
        progress.retrieve_internals(
            query_rows,
            total_chunks=len(merged.chunks),
            graph_context=len(merged.graph_context),
        ),
    )
    return {
        "retrieval": merged,
        "retrieval_mode": mode,
        "warnings": merged.warnings,
        "debug": {
            "retrieve": {
                "mode": mode,
                "queries": query_rows,
                "chunks": len(merged.chunks),
                "graph_context": len(merged.graph_context),
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
    step_id = progress.synthesize_step_id(attempt + 1)
    if attempt > 0:
        # Lượt soạn lại mọc THÊM dòng `synthesize:2`/`validate:2`, không ghi đè dòng cũ —
        # thấy được là hệ thống đã soạn lại mới là điều đáng nói (plan §7.3.1 mục 1).
        await emitter.emit(
            "steps",
            {
                "steps": progress.build_step_list(
                    state.get("route") or "needs_retrieval",
                    state["steps"],
                    attempts=attempt + 1,
                )
            },
        )
    await _emit_step(emitter, step_id, "running")
    settings = get_settings()
    cfg = RuntimeConfig.model_validate(state["runtime_config"])
    retrieval = state["retrieval"]
    assert retrieval is not None  # has_context đảm bảo có chunk trước khi vào đây
    # Document reordering (Phần F): xếp chunk điểm cao ra đầu/cuối prompt, chống "lost in the
    # middle". Thuần layout prompt — KHÔNG đổi retrieval.chunks lưu ở state (citation/viz giữ nguyên).
    # Bỏ chunk provenance-only trước khi reorder: chúng vào tập kết quả để citation trỏ được,
    # KHÔNG phải để đọc. chunk_id của chúng đã có trong khối [QUAN HỆ ĐÃ BIẾT TỪ KNOWLEDGE
    # GRAPH] (kèm "nguồn: ...") nên LLM vẫn trích dẫn được mà không tốn ~2.6K ký tự/chunk.
    chunks_for_prompt = reorder_for_context(answer_context_chunks(retrieval.chunks))
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
    await _emit_step(
        emitter,
        step_id,
        progress.synthesize_state(result.confidence),
        progress.synthesize_detail(
            context_count=len(chunks_for_prompt), confidence=result.confidence
        ),
        progress.synthesize_internals(
            prompt_chunks=len(chunks_for_prompt),
            citation_only_chunks=len(retrieval.chunks) - len(chunks_for_prompt),
            model=_orchestrator_model(),
            attempt=attempt + 1,
        ),
    )
    return {
        "answer": result.answer,
        "used_chunk_ids": result.used_chunk_ids,
        "confidence": result.confidence,
        "synthesize_attempt_count": attempt + 1,
    }


# --- 5b. validate_citations + after_validate (B5) ---


async def validate_citations(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    """Giữ lại các `used_chunk_ids` CÓ THẬT trong tập vừa truy hồi (dedupe, giữ thứ tự).

    KHÔNG gọi LLM — reflection bằng CODE. Và phải nói rõ giới hạn: đây là phép kiểm **hình
    thức** (id có thuộc tập truy hồi không), KHÔNG kiểm câu văn có được đoạn đó chống lưng
    hay không. Ca "trích một chunk có thật nhưng chunk đó nói điều khác" vẫn lọt.

    Phép lọc này trước nằm inline trong `build_visualization` và **vứt id lạ trong im
    lặng**: LLM bịa sạch id thì câu trả lời vẫn hiện kèm dấu [1][2] mà khối Nguồn rỗng, không
    log, không thử lại. Tách ra node riêng là để `after_validate` còn có chỗ mà phản ứng.
    """
    emitter = _emitter(config)
    retrieval = state.get("retrieval")
    available = {c.chunk_id for c in (retrieval.chunks if retrieval else [])}
    claimed = list(dict.fromkeys(state.get("used_chunk_ids", [])))
    valid = [cid for cid in claimed if cid in available]

    settings = get_settings()
    attempt = state.get("synthesize_attempt_count", 0)
    will_retry = not valid and attempt < settings.synthesize_max_attempts
    await emitter.emit(
        "status", {"node": "validate_citations", "msg": "đang đối chiếu trích dẫn"}
    )
    dropped = [cid for cid in claimed if cid not in available]
    await _emit_step(
        emitter,
        progress.validate_step_id(attempt),
        progress.validate_state(len(valid)),
        progress.validate_detail(
            valid=len(valid), total=len(claimed), will_retry=will_retry
        ),
        progress.validate_internals(
            claimed=len(claimed), valid=len(valid), dropped=dropped, will_retry=will_retry
        ),
    )
    return {
        "used_chunk_ids": valid,
        "debug": {
            "validate_citations": {
                "claimed": len(claimed),
                "valid": len(valid),
                "dropped": dropped,
                "will_retry": will_retry,
            }
        },
    }


def after_validate(state: AgentState) -> str:
    """Conditional edge — CHỈ ĐỌC state (không emit, không ghi).

    Thứ tự nhánh có ý nghĩa: `confidence="không đủ dữ liệu"` là LLM tự khai không trả lời
    được, soạn lại cũng vô ích nên đi honest luôn, không tốn lượt.
    """
    if state.get("confidence") == "không đủ dữ liệu":
        return "honest_answer"
    if state.get("used_chunk_ids"):
        return "build_visualization"
    # 0 liên kết hợp lệ: còn lượt thì soạn lại, hết lượt thì thà nói chưa đủ dữ liệu còn hơn
    # đưa ra câu trả lời không có nguồn nào chống lưng.
    if state.get("synthesize_attempt_count", 0) < get_settings().synthesize_max_attempts:
        return "synthesize"
    return "honest_answer"


# --- 6. citation helpers (dùng trong build_visualization) ---


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
    if state.get("selected_mode") == "graph" and retrieval is not None and not retrieval.chunks:
        return GRAPH_EMPTY_MESSAGE
    return HONEST_MESSAGE


async def honest_answer(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    if state.get("synthesize_attempt_count", 0) > 0:
        # synthesize đã stream answer (rồi bị loại) -> clear trước khi stream honest text.
        await emitter.emit("regenerating", {})
    await emitter.emit("status", {"node": "honest_answer", "msg": "chưa đủ dữ liệu"})
    # Chốt dòng soạn bài CHỈ khi nó chưa từng chạy (`retrieve` ra 0 chunk -> has_context đưa
    # thẳng sang đây). Đến từ `after_validate` hết lượt thì các dòng soạn/đối chiếu đã có
    # trạng thái thật rồi, đạp lại là xoá mất chuyện đã xảy ra. Route khác needs_retrieval
    # (out_of_scope) không có dòng nào để chốt.
    if state.get("route") == "needs_retrieval" and state.get("synthesize_attempt_count", 0) == 0:
        await _emit_step(
            emitter,
            progress.synthesize_step_id(1),
            "partial",
            "Chưa đủ dữ liệu · trả lời trung thực",
        )
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


# --- 9. build_visualization (dựng Citation + viz; viz fail không làm fail answer) ---


async def build_visualization(state: AgentState, config: RunnableConfig) -> dict[str, Any]:
    emitter = _emitter(config)
    retrieval = state.get("retrieval")
    chunks_by_id = {c.chunk_id: c for c in (retrieval.chunks if retrieval else [])}
    # KHÔNG lọc ở đây nữa — `validate_citations` đã lọc và mọi id còn lại chắc chắn có trong
    # `chunks_by_id`. Node này chỉ dựng Citation.
    citations = [_build_citation(chunks_by_id[cid]) for cid in state.get("used_chunk_ids", [])]
    await emitter.emit(
        "citations", {"citations": [c.model_dump() for c in citations]}
    )
    await _emit_step(emitter, progress.VISUALIZATION_STEP_ID, "running")
    used_ids = [c.chunk_id for c in citations]
    out: dict[str, Any] = {"citations": citations}
    viz = None
    failure: str | None = None
    try:
        viz = await asyncio.to_thread(build_visualization_payload, used_ids)
    except Exception as exc:  # noqa: BLE001 — viz lỗi không được làm fail answer (plan)
        failure = type(exc).__name__
        out["warnings"] = [f"visualization lỗi: {failure}"]
    await emitter.emit(
        "visualization", {"visualization": viz.model_dump() if viz else None}
    )
    # Viz hỏng -> `partial` kèm tên lỗi, KHÔNG im lặng: đây đúng ca đã cắn một lần rồi
    # (gazetteer chưa có bảng -> UndefinedTable nuốt sạch timeline, xem CLAUDE.md). Lần sau
    # hỏng kiểu đó thì nó hiện ngay trên panel thay vì phải đi đọc log.
    if failure is not None:
        await _emit_step(
            emitter,
            progress.VISUALIZATION_STEP_ID,
            "partial",
            "Không dựng được",
            [{"label": "Lỗi", "value": failure}],
        )
    else:
        counts = {
            "event_count": viz.event_count if viz else 0,
            "marker_count": len(viz.markers) if viz else 0,
            "timeline_count": len(viz.timeline) if viz else 0,
            "unplaced": viz.unplaced_count if viz else 0,
        }
        await _emit_step(
            emitter,
            progress.VISUALIZATION_STEP_ID,
            progress.visualization_state(counts["event_count"]),
            progress.visualization_detail(**counts),
            progress.visualization_internals(**counts),
        )
    out["visualization"] = viz
    return out
