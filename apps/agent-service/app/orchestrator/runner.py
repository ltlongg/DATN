"""Entrypoint chạy answer graph. `run_ask` (stream=False) gom state cuối -> AskResponse.
`run_ask_stream` (SSE) thêm ở phase streaming.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from app.core.runtime_config import get_runtime_config
from app.orchestrator.emitter import Emitter, NullEmitter, QueueEmitter
from app.orchestrator.errors import GuardrailsBlocked, SynthesisError
from app.orchestrator.graph import get_graph
from app.orchestrator.state import AgentState
from app.schemas.ask import AskRequest, AskResponse
from app.schemas.retrieval import RetrievalBackendError


def initial_state(request: AskRequest) -> AgentState:
    return {
        "question": request.question,
        "history": list(request.history),
        # Điền default rỗng ({} -> RuntimeConfig mặc định khi node model_validate); giá trị
        # thật do prepare_state() nhét vào trước khi vào graph.
        "runtime_config": {},
        "user_id": request.user_id,
        "conversation_id": request.conversation_id,
        "message_id": request.message_id,
        "standalone_query": "",
        "steps": [],
        "current_step": 0,
        "resolved": {},
        "resolved_facts": [],
        "stop_reason": "",
        "override_mode": request.mode,
        # Giá trị thật do `plan` giải (auto -> agent chọn; else -> chính override). Đặt
        # "hybrid" làm chỗ giữ chỗ; không node nào đọc trước khi `plan` chạy xong.
        "selected_mode": "hybrid",
        "route": None,
        "clarification_needed": False,
        "clarification_question": None,
        "retrieval": None,
        "retrieval_mode": "none",
        "answer": None,
        "confidence": None,
        "synthesize_attempt_count": 0,
        "used_chunk_ids": [],
        "citations": [],
        "visualization": None,
        "warnings": [],
        "debug": {},
    }


async def prepare_state(request: AskRequest) -> AgentState:
    """State khởi tạo + snapshot runtime_config (gọi backend đúng 1 LẦN/request, cache TTL).
    Mọi node sau chỉ đọc từ state["runtime_config"], không gọi lại/không I/O."""
    state = initial_state(request)
    cfg = await asyncio.to_thread(get_runtime_config)
    state["runtime_config"] = cfg.model_dump()
    return state


def build_response(request: AskRequest, state: dict[str, Any]) -> AskResponse:
    debug = state.get("debug") if request.debug else None
    if state.get("clarification_needed"):
        return AskResponse(
            clarification_needed=True,
            clarification_question=state.get("clarification_question"),
            retrieval_mode="none",
            warnings=state.get("warnings", []),
            debug=debug,
        )
    return AskResponse(
        answer=state.get("answer"),
        citations=state.get("citations", []),
        retrieval_mode=state.get("retrieval_mode", "none"),
        confidence=state.get("confidence"),
        visualization=state.get("visualization"),
        warnings=state.get("warnings", []),
        debug=debug,
    )


async def run_ask(request: AskRequest, *, emitter: Emitter | None = None) -> AskResponse:
    """Chạy graph tới hết, dựng AskResponse từ state cuối (đường stream=False).

    Guardrails chặn input -> GuardrailsBlocked: trả AskResponse với safe message (đường
    non-stream không có event `blocked`, gói gọn vào answer)."""
    emitter = emitter or NullEmitter()
    try:
        final = await get_graph().ainvoke(
            await prepare_state(request), config={"configurable": {"emitter": emitter}}
        )
    except GuardrailsBlocked as blocked:
        return AskResponse(answer=blocked.safe_message, retrieval_mode="none")
    return build_response(request, final)


# --- streaming (SSE) ---

_SENTINEL = object()


def _sse(event_type: str, data: dict[str, object]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def error_code(exc: BaseException) -> str:
    if isinstance(exc, (RetrievalBackendError, SynthesisError)):
        return exc.code
    return "internal_error"


def error_message(exc: BaseException) -> str:
    """Message an toàn — KHÔNG dump stack/secret (cả SSE lẫn HTTP body)."""
    mapping = {
        "all_backends_failed": "Không truy cập được nguồn dữ liệu.",
        "qdrant_unavailable": "Không truy cập được kho vector.",
        "neo4j_unavailable": "Không truy cập được knowledge graph.",
        "embedding_failed": "Không sinh được embedding cho câu hỏi.",
        "refusal": "Mô hình từ chối tạo câu trả lời.",
        "empty_synthesis": "Không tạo được câu trả lời.",
    }
    return mapping.get(error_code(exc), "Có lỗi xảy ra khi xử lý câu hỏi.")


async def run_ask_stream(request: AskRequest) -> AsyncIterator[str]:
    """Chạy graph, stream SSE: status* -> token* -> citations -> visualization -> done.
    Lỗi sau khi SSE đã mở đi qua event `error` (không đổi HTTP status). clarify -> emit
    `clarification` + `done`, không token."""
    emitter = QueueEmitter()
    final_state: dict[str, Any] = {}
    captured: dict[str, BaseException] = {}
    state = await prepare_state(request)

    async def _run() -> None:
        try:
            result = await get_graph().ainvoke(
                state, config={"configurable": {"emitter": emitter}}
            )
            final_state.update(result)
        except Exception as exc:  # noqa: BLE001 — sau khi SSE mở, lỗi đi qua event error
            captured["error"] = exc
        finally:
            await emitter.queue.put(_SENTINEL)  # type: ignore[arg-type]

    task = asyncio.create_task(_run())
    try:
        while True:
            item = await emitter.queue.get()
            if item is _SENTINEL:
                break
            event_type, data = item
            yield _sse(event_type, data)

        exc = captured.get("error")
        if exc is not None:
            # GuardrailsBlocked đã emit `blocked` và dừng — không thêm error event.
            if not isinstance(exc, GuardrailsBlocked):
                yield _sse("error", {"code": error_code(exc), "message": error_message(exc)})
            return
        if request.debug:
            # Gom debug (plan + retrieve) rồi bắn 1 lần, NGAY TRƯỚC done. Xem
            # backend-additions-plan.md §1.1: dữ liệu có sớm nhưng gửi muộn (đọc từ
            # final_state sau khi graph xong) — hành vi cố ý, FE hiện placeholder tới lúc này.
            yield _sse("debug", {"debug": final_state.get("debug", {})})
        yield _sse(
            "done",
            {
                "confidence": final_state.get("confidence"),
                "retrieval_mode": final_state.get("retrieval_mode", "none"),
                "warnings": final_state.get("warnings", []),
            },
        )
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
