"""Module 4 — Hội thoại & chất lượng router (admin, read-only) — prefix /api/admin/logs.

Chất lượng suy ra bằng hàm thuần quality_service (không lưu cột riêng). Xem
backend-additions-plan.md §3.1.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin
from app.core.errors import AppError
from app.models import logs as repo
from app.schemas.logs import (
    ConversationLogDetail,
    ConversationLogItem,
    ConversationLogResponse,
    MessageLogItem,
    MessageTokens,
    QualitySummary,
    TokenSummary,
)
from app.services.quality_service import compute_quality_summary, message_quality_flags
from app.services.token_service import build_message_tokens, compute_token_summary

router = APIRouter(dependencies=[Depends(require_admin)])

@router.get("/conversations", response_model=ConversationLogResponse)
async def list_conversations(
    user_email: str | None = Query(default=None),
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ConversationLogResponse:
    rows, total = await anyio.to_thread.run_sync(
        repo.list_conversations_admin, user_email, from_date, to_date, limit, offset
    )
    return ConversationLogResponse(
        items=[ConversationLogItem(**r) for r in rows], total=total, limit=limit, offset=offset
    )

@router.get("/conversations/{conversation_id}", response_model=ConversationLogDetail)
async def get_conversation(conversation_id: str) -> ConversationLogDetail:
    conv = await anyio.to_thread.run_sync(
        repo.get_conversation_detail_admin, conversation_id
    )
    if conv is None:
        raise AppError(404, "not_found", "Không tìm thấy cuộc trò chuyện.")
    messages = [
        MessageLogItem(**m, quality=message_quality_flags(m)) for m in conv["messages"]
    ]
    return ConversationLogDetail(
        id=conv["id"],
        title=conv["title"],
        user_email=conv["user_email"],
        user_name=conv["user_name"],
        created_at=conv["created_at"],
        updated_at=conv["updated_at"],
        messages=messages,
    )

@router.get("/quality-summary", response_model=QualitySummary)
async def quality_summary(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
) -> QualitySummary:
    rows = await anyio.to_thread.run_sync(repo.list_quality_rows, from_date, to_date)
    return compute_quality_summary(rows)

@router.get("/token-summary", response_model=TokenSummary)
async def token_summary(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
) -> TokenSummary:
    """Card token đầu tab + map token theo hội thoại (chỉ usage đã gắn conversation_id trong
    khoảng ngày). Chỉ lọc theo ngày (giống quality-summary), không theo user_email."""
    rows = await anyio.to_thread.run_sync(
        repo.list_attributed_usage_rows, from_date, to_date
    )
    return compute_token_summary(rows)

@router.get("/conversations/{conversation_id}/tokens", response_model=list[MessageTokens])
async def conversation_tokens(conversation_id: str) -> list[MessageTokens]:
    """Phân rã token theo message + task cho 1 hội thoại (chi tiết)."""
    rows = await anyio.to_thread.run_sync(repo.get_message_token_rows, conversation_id)
    return build_message_tokens(rows)
