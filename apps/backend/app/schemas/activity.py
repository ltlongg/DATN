"""Schema cho activity log (admin, read-only).

Một dòng = một request /api/* đã ghi bởi ActivityLogMiddleware. Xem activity-log-plan.md §4.5.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ActivityLogItem(BaseModel):
    id: str
    created_at: datetime
    request_id: str | None
    user_id: str | None
    method: str
    path: str
    status_code: int
    severity: str  # 'ok' | 'error'
    latency_ms: int | None
    error: str | None


class ActivityLogResponse(BaseModel):
    items: list[ActivityLogItem]
    total: int
    limit: int
    offset: int
