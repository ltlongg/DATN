"""Schema payload visualization (map + timeline) trả cho frontend.

Map và timeline LIÊN KẾT bằng `event_id` (click marker -> highlight timeline item cùng
event_id và ngược lại). Honest fallback (xem CLAUDE.md):
- event thiếu địa điểm/toạ độ -> chỉ có TimelineItem, không MapMarker.
- event thiếu thời gian -> chỉ có MapMarker, không TimelineItem.
- event thiếu cả hai -> không render (đếm vào `unplaced_count`).

`MapMarker.scope` mang `location_scope` của event sang cho UI, vì hai loại marker nói hai
điều KHÁC HẲN nhau và vẽ giống nhau là nói dối:
- 'sites' — sự kiện xảy ra ĐÚNG TẠI điểm này. Vẽ pin đặc, có nhãn.
- 'area'  — sự kiện TRẢI RỘNG, điểm này chỉ là một nơi tiêu biểu được nhắc tên (phong
  trào, địa bàn hoạt động). Vẽ vòng tròn rỗng/mờ. Chọn event -> khớp khung nhìn quanh CẢ
  CỤM điểm thay vì bay tới một điểm.

KHÔNG có polygon và cũng không định có: ranh giới hành chính lịch sử không tra được, còn
bao lồi của các điểm thì vô nghĩa (một event 'area' của Đông Kinh nghĩa thục trải từ Hà
Nội tới Phan Thiết, bao lồi phủ gần trọn Việt Nam). Khung nhìn (bounding box) do UI tự
tính từ chính các marker cùng `event_id` — nó là CHỖ ĐỂ NHÌN, không phải hình được vẽ ra,
nên không cần dữ liệu mới nào.

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
    scope: str
    """`location_scope` của event ('sites' | 'area') — QUYẾT ĐỊNH CÁCH VẼ, xem docstring module."""

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
