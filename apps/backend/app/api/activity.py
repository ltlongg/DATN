"""Activity log router (admin) — prefix /api/admin/activity.

Đọc bảng activity_log (backend-owned, ghi bởi ActivityLogMiddleware) cho feed "Hoạt động hệ
thống". Read-only. Xem activity-log-plan.md §4.6.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin
from app.models import activity as repo
from app.schemas.activity import ActivityLogItem, ActivityLogResponse

router = APIRouter(dependencies=[Depends(require_admin)])

@router.get("", response_model=ActivityLogResponse)
async def list_activity(
    severity: str | None = Query(default=None, pattern="^(ok|error)$"),
    path: str | None = Query(default=None),
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ActivityLogResponse:
    rows, total = await anyio.to_thread.run_sync(
        lambda: repo.list_activity(
            severity=severity,
            path=path,
            from_date=from_date,
            to_date=to_date,
            limit=limit,
            offset=offset,
        )
    )
    return ActivityLogResponse(
        items=[ActivityLogItem(**r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )
