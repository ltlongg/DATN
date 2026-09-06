"""Schema payload visualization (dòng thời gian) trả cho frontend.

Honest fallback (xem docs/project-overview.md):
- event thiếu thời gian -> không lên dòng thời gian, đếm vào `unplaced_count`.

Sinh ONLINE từ events đã retrieve (không pre-compute, không trích mới).

Bản đồ đã gỡ khỏi hệ thống 2026-09-06 — `MapMarker` và field `markers` bỏ theo (cùng
`located`, vốn chỉ để UI biết mốc nào có toạ độ mà chấm lên map).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TimelineItem(BaseModel):
    """Một mốc trên dòng thời gian."""

    event_id: str
    label: str
    summary: str
    time_start: str
    time_end: str | None = None
    confidence: str
    locations: list[str] = Field(default_factory=list)


class VisualizationPayload(BaseModel):
    """Gói dữ liệu render. `unplaced_count` để honest về phần không đủ data hiển thị."""

    timeline: list[TimelineItem] = Field(default_factory=list)
    event_count: int = 0
    unplaced_count: int = 0
