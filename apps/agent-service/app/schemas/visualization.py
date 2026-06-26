"""Schema payload visualization (map + timeline) trả cho frontend.

Map và timeline LIÊN KẾT bằng `event_id` (click marker -> highlight timeline item cùng
event_id và ngược lại). Honest fallback (xem CLAUDE.md):
- event thiếu địa điểm/toạ độ -> chỉ có TimelineItem, không MapMarker.
- event thiếu thời gian -> chỉ có MapMarker, không TimelineItem.
- event thiếu cả hai -> không render (đếm vào `unplaced_count`).

Sinh ONLINE từ events đã retrieve (không pre-compute, không trích mới).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class MapMarker(BaseModel):
    """Một điểm trên bản đồ. Nhiều marker có thể chung `event_id` (sự kiện nhiều nơi)."""

    event_id: str
    label: str
    summary: str
    location: str  # surface form của địa điểm marker này
    lat: float
    lon: float
    confidence: str  # cao/vừa/thấp — YẾU NHẤT giữa event và toạ độ (render đậm/nhạt)
    time_start: str | None = None  # để hiển thị/lọc theo thời gian trên map


class TimelineItem(BaseModel):
    """Một mốc trên dòng thời gian. `located` = có ít nhất 1 marker (để UI link 2 chiều)."""

    event_id: str
    label: str
    summary: str
    time_start: str
    time_end: str | None = None
    confidence: str
    locations: list[str] = Field(default_factory=list)
    located: bool = False


class VisualizationPayload(BaseModel):
    """Gói dữ liệu render. `unplaced_count` để honest về phần không đủ data hiển thị."""

    markers: list[MapMarker] = Field(default_factory=list)
    timeline: list[TimelineItem] = Field(default_factory=list)
    event_count: int = 0
    unplaced_count: int = 0
