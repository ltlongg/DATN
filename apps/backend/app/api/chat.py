"""Chat router — conversations CRUD + /ask (streaming proxy sang agent-service)."""

from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

import anyio
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.deps import get_current_user, get_owned_conversation
from app.core.config import get_settings
from app.models import conversation as conv_repo
from app.models.conversation import Conversation
from app.models.user import User
from app.schemas.chat import (
    AskRequest,
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    MessageOut,
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


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conv: Conversation = Depends(get_owned_conversation),
) -> ConversationDetail:
    messages = await anyio.to_thread.run_sync(conv_repo.list_messages, conv.id)
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=[
            MessageOut(**m.model_dump(exclude={"conversation_id"})) for m in messages
        ],
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


async def _proxy_stream(
    stream: AgentStream, collector: SseCollector, conversation_id: str, assistant_id: str
) -> AsyncIterator[str]:
    """Proxy event SSE xuống frontend, gom vào collector, lưu message cuối khi `done`.

    - event != done: forward nguyên (không sửa nội dung token).
    - event == done: lưu assistant message rồi forward done đã thêm conversation_id/
      message_id (message_id=None nếu không lưu) để frontend link được message.
    """
    async for event in stream.events():
        collector.feed(event.event, event.data)
        if event.event == "done":
            saved_id = await _persist_assistant(conversation_id, assistant_id, collector)
            logger.info(
                "ask done conversation=%s confidence=%s mode=%s citations=%d warnings=%d",
                conversation_id,
                collector.confidence,
                collector.retrieval_mode,
                len(collector.citations),
                len(collector.warnings),
            )
            yield format_sse(
                "done",
                {**event.data, "conversation_id": conversation_id, "message_id": saved_id},
            )
        else:
            yield format_sse(event.event, event.data)
            if event.event == "error":
                logger.info(
                    "ask error conversation=%s code=%s",
                    conversation_id,
                    (collector.error or {}).get("code"),
                )


@router.post("/conversations/{conversation_id}/ask")
async def ask(
    body: AskRequest, conv: Conversation = Depends(get_owned_conversation)
) -> StreamingResponse:
    settings = get_settings()

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
        question=body.question, history=history, mode=body.mode, stream=True, debug=body.debug
    )
    stream = await open_ask_stream(agent_request)

    collector = SseCollector()
    return StreamingResponse(
        _proxy_stream(stream, collector, conv.id, assistant_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
