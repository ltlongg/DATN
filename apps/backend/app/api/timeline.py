"""Router trang "Dòng lịch sử" (user) — prefix /api/timeline.

CHỈ cần đăng nhập, không gác admin: cùng lý do với `GET /api/chat/sources/{chunk_id}` —
corpus là SGK, không mật. Đọc thẳng `timeline_events` đã index sẵn: KHÔNG gọi
agent-service, KHÔNG tốn LLM call nào.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.models import timeline as repo
from app.schemas.timeline import TimelineCard, TimelineCardsResponse

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/events", response_model=TimelineCardsResponse)
async def list_timeline_cards(
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> TimelineCardsResponse:
    rows, total = await anyio.to_thread.run_sync(repo.list_timeline_cards, limit, offset)
    return TimelineCardsResponse(
        items=[TimelineCard(**r) for r in rows], total=total, limit=limit, offset=offset
    )
