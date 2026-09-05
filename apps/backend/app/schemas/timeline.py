"""Schema trang "Dòng lịch sử" (user). Mirror app/models/timeline.py.

Cố ý KHÔNG có `source_chunk_ids`: trang này để đọc dòng chảy lịch sử, không phải để soi
provenance (đã có KB Inspector bên admin và danh sách nguồn bên trang hỏi đáp). Cột đó
chỉ dùng phía server để giữ thứ tự đọc của sách.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TimelineCard(BaseModel):
    """Một sự kiện trên trục. `summary` trả LUÔN trong danh sách (30 item/trang, không
    đáng kể) để click thẻ trải chi tiết tại chỗ, khỏi cần endpoint detail riêng."""

    event_id: str
    label: str
    summary: str
    # Không bao giờ None: model lọc `time_sort IS NOT NULL`.
    time_start: str
    time_end: str | None = None
    locations: list[str] = Field(default_factory=list)
    confidence: str


class TimelineCardsResponse(BaseModel):
    items: list[TimelineCard]
    total: int
    limit: int
    offset: int
