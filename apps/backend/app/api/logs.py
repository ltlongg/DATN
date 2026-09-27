"""Module 4 — Hội thoại & chất lượng router (admin, read-only) — prefix /api/admin/logs.

Chất lượng suy ra bằng hàm thuần quality_service (không lưu cột riêng). Xem
backend-additions-plan.md §3.1. Admin thấy gì (nội dung/danh tính) do privacy_service quyết.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends, Query, Request

from app.api.deps import require_admin
from app.core.config import get_settings
from app.core.errors import AppError
from app.models import logs as repo
from app.models.activity import record_activity
from app.models.user import User
from app.schemas.logs import (
    ConversationLogDetail,
    ConversationLogItem,
    ConversationLogResponse,
    MessageLogItem,
    MessageTokens,
    QualitySummary,
    TokenSummary,
)
from app.services.privacy_service import message_visibility, redact_message, reveal_identity
from app.services.quality_service import compute_quality_summary, message_quality_flags
from app.services.token_service import build_message_tokens, compute_token_summary

router = APIRouter(dependencies=[Depends(require_admin)])

@router.get("/conversations", response_model=ConversationLogResponse)
async def list_conversations(
    user_anon_id: str | None = Query(default=None),
    flagged_only: bool = Query(default=False),
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ConversationLogResponse:
    rows, total = await anyio.to_thread.run_sync(
        repo.list_conversations_admin,
        get_settings().backend_secret_key,
        user_anon_id,
        flagged_only,
        from_date,
        to_date,
        limit,
        offset,
    )
    items = []
    for r in rows:
        identity = reveal_identity(r["flagged_count"])
        items.append(
            ConversationLogItem(
                id=r["id"],
                title=r["title"] if r["shared"] else None,
                user_anon_id=r["user_anon_id"],
                user_email=r["user_email"] if identity else None,
                user_name=r["user_name"] if identity else None,
                shared=r["shared"],
                flagged_count=r["flagged_count"],
                message_count=r["message_count"],
                created_at=r["created_at"],
                updated_at=r["updated_at"],
            )
        )
    return ConversationLogResponse(items=items, total=total, limit=limit, offset=offset)

@router.get("/conversations/{conversation_id}", response_model=ConversationLogDetail)
async def get_conversation(
    conversation_id: str, request: Request, admin: User = Depends(require_admin)
) -> ConversationLogDetail:
    conv = await anyio.to_thread.run_sync(
        repo.get_conversation_detail_admin, get_settings().backend_secret_key, conversation_id
    )
    if conv is None:
        raise AppError(404, "not_found", "Không tìm thấy cuộc trò chuyện.")

    raw = conv["messages"]
    visibility = message_visibility(raw, conv["shared"])
    messages = [
        MessageLogItem(
            # Chất lượng tính trên bản THÔ (cần citations) trước khi ẩn.
            **(m if vis != "hidden" else redact_message(m)),
            visibility=vis,
            quality=message_quality_flags(m),
        )
        for m, vis in zip(raw, visibility)
    ]
    flagged_count = sum(1 for m in raw if m["flagged"])
    identity = reveal_identity(flagged_count)

    # Middleware đã log mọi lượt mở; thêm 1 dòng riêng khi lượt này THẬT SỰ lộ nội dung hoặc
    # danh tính, để trang Hoạt động phân biệt được với lượt chỉ xem số liệu.
    shown_shared = visibility.count("shared")
    shown_flagged = visibility.count("flagged")
    if shown_shared or shown_flagged or identity:
        note = f"{shown_shared} tin chia sẻ, {shown_flagged} tin gắn cờ"
        if identity:
            note += ", lộ danh tính"
        await anyio.to_thread.run_sync(
            lambda: record_activity(
                request_id=getattr(request.state, "request_id", None),
                user_id=admin.id,
                method="GET",
                path=f"{request.url.path} (xem nội dung: {note})",
                status_code=200,
                severity="ok",
                latency_ms=None,
                error=None,
            )
        )

    return ConversationLogDetail(
        id=conv["id"],
        title=conv["title"] if conv["shared"] else None,
        user_anon_id=conv["user_anon_id"],
        user_email=conv["user_email"] if identity else None,
        user_name=conv["user_name"] if identity else None,
        shared=conv["shared"],
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
    khoảng ngày). Chỉ lọc theo ngày (giống quality-summary), không theo người dùng."""
    rows = await anyio.to_thread.run_sync(
        repo.list_attributed_usage_rows, from_date, to_date
    )
    return compute_token_summary(rows)

@router.get("/conversations/{conversation_id}/tokens", response_model=list[MessageTokens])
async def conversation_tokens(conversation_id: str) -> list[MessageTokens]:
    """Phân rã token theo message + task cho 1 hội thoại (chi tiết)."""
    rows = await anyio.to_thread.run_sync(repo.get_message_token_rows, conversation_id)
    return build_message_tokens(rows)
