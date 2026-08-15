"""Chat router — conversations CRUD + /ask (streaming proxy sang agent-service)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Any

import anyio
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user, get_owned_conversation
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import conversation as conv_repo
from app.models import inspect as inspect_repo
from app.models.activity import record_activity
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.chat import (
    AskRequest,
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    ConversationUpdate,
    MessageOut,
    SourceDetail,
)
from app.services.agent_client import (
    AgentAskRequest,
    AgentStream,
    format_sse,
    open_ask_stream,
)
from app.services.conversation_service import (
    DEFAULT_TITLE,
    build_bounded_history,
    derive_title,
)
from app.services.sse_collector import SseCollector

logger = logging.getLogger("backend.chat")

router = APIRouter()

def _to_out(conv: Conversation) -> ConversationOut:
    return ConversationOut(
        id=conv.id, title=conv.title, created_at=conv.created_at, updated_at=conv.updated_at
    )

@router.post("/conversations", response_model=ConversationOut, status_code=201)
async def create_conversation(
    body: ConversationCreate, user: User = Depends(get_current_user)
) -> ConversationOut:
    title = (body.title or "").strip() or DEFAULT_TITLE
    conv = await anyio.to_thread.run_sync(conv_repo.create_conversation, user.id, title)
    return _to_out(conv)

@router.get("/conversations", response_model=list[ConversationOut])
async def list_conversations(user: User = Depends(get_current_user)) -> list[ConversationOut]:
    convs = await anyio.to_thread.run_sync(conv_repo.list_conversations, user.id)
    return [_to_out(c) for c in convs]

@router.patch("/conversations/{conversation_id}", response_model=ConversationOut)
async def rename_conversation(
    body: ConversationUpdate,
    conv: Conversation = Depends(get_owned_conversation),
) -> ConversationOut:
    title = body.title.strip()
    if not title:
        raise AppError(422, "invalid_title", "Tên cuộc trò chuyện không được để trống.")
    await anyio.to_thread.run_sync(conv_repo.update_title, conv.id, title)
    return _to_out(conv.model_copy(update={"title": title}))

@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(
    conv: Conversation = Depends(get_owned_conversation),
) -> None:
    await anyio.to_thread.run_sync(conv_repo.delete_conversation, conv.id)

@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conv: Conversation = Depends(get_owned_conversation),
    user: User = Depends(get_current_user),
) -> ConversationDetail:
    messages = await anyio.to_thread.run_sync(conv_repo.list_messages, conv.id)
    # `steps` lưu KÈM internals (để admin soi lại ở /admin/logs) nên đường đọc lại phải gác
    # y như đường stream — chặn mỗi lúc chạy rồi mở toang lúc F5 thì coi như không chặn.
    keep_internals = user.role == "admin"
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            MessageOut(
                **{
                    **m.model_dump(exclude={"conversation_id"}),
                    "steps": [_visible_step(s, keep_internals) for s in m.steps],
                }
            )
            for m in messages
        ],
    )

# --- xem nguồn (citation-viewer-plan §4) ---

@router.get("/sources/{chunk_id}", response_model=SourceDetail)
async def get_source(chunk_id: str, user: User = Depends(get_current_user)) -> SourceDetail:
    """Toàn văn chunk đứng sau 1 citation — user nhấn `[n]` ở khối Nguồn thì gọi vào đây.

    CHỈ cần đăng nhập (KHÔNG `require_admin`): corpus là SGK lịch sử, không phải dữ liệu
    mật, và user vốn đã đọc được nội dung đó qua chính câu trả lời. Router
    `/api/admin/kb/*` vẫn gác admin như cũ — xem plan §4.
    """
    chunk = await anyio.to_thread.run_sync(inspect_repo.get_chunk, chunk_id)
    if chunk is None:
        raise AppError(404, "not_found", "Không tìm thấy nguồn.")
    meta = chunk["metadata"] or {}
    return SourceDetail(
        chunk_id=chunk["chunk_id"],
        text=chunk["text"],
        heading_path=chunk["heading_path"] or [],
        start_line=meta.get("start_line"),
        end_line=meta.get("end_line"),
    )

async def _persist_assistant(
    conversation_id: str, assistant_id: str, collector: SseCollector
) -> str | None:
    """Lưu assistant message từ collector (dùng id đã pre-generate). Trả id nếu lưu, None
    nếu không có gì đáng lưu (error/blocked/rỗng)."""
    if not collector.should_persist():
        return None
    await anyio.to_thread.run_sync(
        lambda: conv_repo.add_message(
            conversation_id, message_id=assistant_id, **collector.message_fields()
        )
    )
    await anyio.to_thread.run_sync(conv_repo.touch_conversation, conversation_id)
    return assistant_id

def _visible_step(data: dict[str, Any], debug: bool) -> dict[str, Any]:
    """Bóc `internals` (tầng 2 của panel tiến trình) khỏi event `step` khi không phải admin.

    Agent LUÔN gửi internals để `collector` lưu được bản đầy đủ vào `messages.steps`; chỗ
    quyết định ai được XEM là đây. Giấu ở frontend thôi thì không tính — dữ liệu vẫn nằm
    trong tab Network, tức nới lỏng thế phòng thủ mà `debug` đang giữ (xem `ask()` bên dưới).
    """
    if debug or "internals" not in data:
        return data
    return {k: v for k, v in data.items() if k != "internals"}

async def _proxy_stream(
    stream: AgentStream,
    collector: SseCollector,
    conversation_id: str,
    assistant_id: str,
    request_id: str | None,
    user_id: str,
    started_at: float,
    debug: bool,
) -> AsyncIterator[str]:
    """Proxy event SSE xuống frontend, gom vào collector, lưu message cuối khi `done`.

    - event != done/blocked: forward nguyên (không sửa nội dung token), TRỪ `step` của người
      dùng thường — xem `_visible_step`.
    - event == token: chốt TTFT ở token ĐẦU TIÊN (mốc `started_at` bấm từ đầu handler ask()),
      tức đúng khoảng người dùng chờ từ lúc hỏi tới lúc thấy chữ đầu tiên.
    - event == done: lưu assistant message rồi forward done đã thêm conversation_id/
      message_id (message_id=None nếu không lưu) + ttft_ms để frontend hiện ngay, khỏi reload.
    - event == blocked: guardrails chặn input -> agent KHÔNG emit done. Persist safe message
      (nếu có content) NGAY tại đây rồi forward blocked nguyên (event realtime, không kèm id).
    """
    async for event in stream.events():
        if event.event == "token" and collector.ttft_ms is None:
            collector.mark_first_token(int((perf_counter() - started_at) * 1000))
        collector.feed(event.event, event.data)
        if event.event == "done":
            saved_id = await _persist_assistant(conversation_id, assistant_id, collector)
            logger.info(
                "ask done conversation=%s confidence=%s mode=%s citations=%d warnings=%d "
                "ttft_ms=%s",
                conversation_id,
                collector.confidence,
                collector.retrieval_mode,
                len(collector.citations),
                len(collector.warnings),
                collector.ttft_ms,
            )
            yield format_sse(
                "done",
                {
                    **event.data,
                    "conversation_id": conversation_id,
                    "message_id": saved_id,
                    "ttft_ms": collector.ttft_ms,
                },
            )
        elif event.event == "blocked":
            saved_id = await _persist_assistant(conversation_id, assistant_id, collector)
            logger.info(
                "ask blocked conversation=%s persisted=%s categories=%s",
                conversation_id,
                saved_id is not None,
                event.data.get("categories"),
            )
            yield format_sse("blocked", event.data)
        elif event.event == "step":
            # collector.feed() ở trên đã nhận bản ĐẦY ĐỦ -> DB có internals; chỉ bản chảy
            # xuống trình duyệt mới bị bóc.
            yield format_sse("step", _visible_step(event.data, debug))
        else:
            yield format_sse(event.event, event.data)
            if event.event == "error":
                code = (collector.error or {}).get("code")
                logger.info("ask error conversation=%s code=%s", conversation_id, code)
                # HTTP response đã mở 200 từ trước (xem ask()) — lỗi này chỉ lộ giữa stream
                # SSE nên middleware activity log không bắt được. Ghi thêm 1 dòng riêng để
                # admin thấy trên trang Hoạt động hệ thống (activity-log-plan.md không cover
                # ca này — bổ sung theo yêu cầu 2026-07-05).
                await anyio.to_thread.run_sync(
                    lambda: record_activity(
                        request_id=request_id,
                        user_id=user_id,
                        method="POST",
                        path=f"/api/conversations/{conversation_id}/ask (stream)",
                        status_code=200,
                        severity="error",
                        latency_ms=None,
                        error=str(code) if code else "stream_error",
                    )
                )

@router.post("/conversations/{conversation_id}/ask")
async def ask(
    request: Request,
    body: AskRequest,
    conv: Conversation = Depends(get_owned_conversation),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    settings = get_settings()
    # Mốc TTFT: bấm giờ NGAY đầu handler (trước quota/history/mở stream agent) để con số đo
    # đúng cái người dùng chờ, không chỉ phần LLM. Chốt ở token đầu trong _proxy_stream.
    started_at = perf_counter()

    # Gác server-side: chỉ admin được bật debug. User gửi debug=true bị ép False (phòng thủ
    # kép với FE). Cờ này giờ gác HAI thứ: event `debug` (agent chỉ phát khi request.debug)
    # và `internals` trong event `step` (agent luôn gửi, backend bóc — xem `_visible_step`).
    debug = body.debug and user.role == "admin"

    # Quota: kiểm NGAY ĐẦU, TRƯỚC add_message câu hiện tại. count_user_messages_today đếm cả
    # message vừa lưu -> nếu check sau add_message thì quota=1 chặn nhầm ngay câu đầu (off-by-
    # one). Vượt -> 429, chưa lưu message, chưa mở stream.
    if user.question_quota is not None:
        used_today = await anyio.to_thread.run_sync(
            conv_repo.count_user_messages_today, user.id
        )
        if used_today >= user.question_quota:
            raise AppError(
                429,
                "quota_exceeded",
                f"Bạn đã dùng hết quota {user.question_quota} câu hỏi hôm nay.",
            )

    # 1) Bounded history = các lượt TRƯỚC (chưa gồm câu hỏi hiện tại, vốn đi field riêng).
    prior = await anyio.to_thread.run_sync(conv_repo.list_messages, conv.id)
    history = build_bounded_history(prior, settings.ask_max_history_messages)

    # 2) Câu hỏi đầu tiên + title còn mặc định -> đặt title suy từ câu hỏi (không gọi LLM).
    if not prior and conv.title == DEFAULT_TITLE:
        await anyio.to_thread.run_sync(
            conv_repo.update_title, conv.id, derive_title(body.question)
        )

    # 3) Lưu user message + bump conversation lên đầu danh sách.
    await anyio.to_thread.run_sync(
        lambda: conv_repo.add_message(conv.id, "user", body.question)
    )
    await anyio.to_thread.run_sync(conv_repo.touch_conversation, conv.id)

    # 4) message_id assistant pre-generate -> chèn vào event done dù nội dung còn đang stream.
    assistant_id = str(uuid.uuid4())

    # 5) Mở stream agent TRƯỚC khi trả StreamingResponse: lỗi connect/status còn map được
    # HTTP 503/504/502 (open_ask_stream ném AppError -> handler trả status, chưa mở SSE).
    agent_request = AgentAskRequest(
        question=body.question,
        history=history,
        mode=body.mode,
        stream=True,
        debug=debug,
        user_id=user.id,
        conversation_id=conv.id,
        message_id=assistant_id,
    )
    stream = await open_ask_stream(agent_request)

    collector = SseCollector()
    request_id = getattr(request.state, "request_id", None)
    return StreamingResponse(
        _proxy_stream(
            stream, collector, conv.id, assistant_id, request_id, user.id, started_at, debug
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
