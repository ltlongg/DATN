"""Schema cho LLM geocode địa danh lịch sử Việt Nam -> toạ độ.

Dùng làm `response_format` cho OpenAI Structured Outputs (strict json_schema).
Strict mode KHÔNG cho default => mọi field bắt buộc; dùng giá trị "rỗng" quy ước
(0.0 cho lat/lon khi không định vị được, "" cho chuỗi) thay cho `None`.

LƯU Ý phạm vi: `GeocodeResult` GIÀU hơn cột bảng `gazetteer` (đã cắt admin_level/
modern_name/note). Các field phụ trợ ở đây chảy vào `dataset/gazetteer_review.md`
để review tay, KHÔNG vào DB.

`GeocodeContext` + `LocationToGeocode` là ĐẦU VÀO của pipeline (rút từ
`timeline_events`), không phải output của LLM — xem `app/indexing/geocoding/context.py`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

class GeocodeContext(BaseModel):
    """Ngữ cảnh của MỘT địa danh, rút từ các event đã trích chứa nó.

    Lý do tồn tại: geocode một cái tên trần trụi là bài toán thiếu dữ kiện — "làng Thanh
    Thuỷ" có ở nhiều tỉnh, "A1" tự nó vô nghĩa. Bốn trường dưới đây là toàn bộ manh mối
    lấy được từ `timeline_events` mà KHÔNG phải join sang kho chunk.

    Mọi trường có thể rỗng (địa danh chỉ xuất hiện một lần, đứng một mình, không mốc).
    """

    anchors: list[str] = Field(
        default_factory=list,
        description="`location_anchor` của các event chứa địa danh này — vùng bao, mạnh nhất.",
    )
    neighbors: list[str] = Field(
        default_factory=list,
        description="Địa danh khác xuất hiện CÙNG event -> nhiều khả năng lân cận.",
    )
    events: list[str] = Field(
        default_factory=list,
        description="Nhãn event tiêu biểu, cho biết bối cảnh lịch sử của địa danh.",
    )
    period: str = Field(
        default="",
        description="Khoảng năm các event diễn ra ('1954' hoặc '1859-1885'). '' nếu không mốc.",
    )

    def is_empty(self) -> bool:
        return not (self.anchors or self.neighbors or self.events or self.period)

class LocationToGeocode(BaseModel):
    """Một địa danh cần geocode: khoá chuẩn hoá + surface hiển thị + tần suất + ngữ cảnh."""

    norm: str  # normalize_name(display) — khoá của bảng `gazetteer` và của cache
    display: str  # surface form phổ biến nhất, dùng làm truy vấn geocode
    count: int  # số event tham chiếu (để lọc --min-count và sắp review)
    context: GeocodeContext

class GeocodeResult(BaseModel):
    """Toạ độ + thông tin phụ trợ cho một địa danh."""

    lat: float = Field(
        description=(
            "Vĩ độ (WGS84). Địa danh trong VN: khoảng 8.0–23.5. Địa danh THỰC SỰ ở "
            "ngoài VN (Paris, Quảng Tây...): trả toạ độ thật của nó (nằm ngoài khoảng "
            "trên là đúng). Dùng 0.0 nếu KHÔNG xác định được vị trí (confidence='thấp')."
        )
    )
    lon: float = Field(
        description=(
            "Kinh độ (WGS84). Trong VN: khoảng 102.0–110.0; ngoài VN: toạ độ thật của "
            "địa danh. Dùng 0.0 nếu không xác định được."
        )
    )
    confidence: Literal["cao", "vừa", "thấp"] = Field(
        description=(
            "Độ chắc chắn của toạ độ: 'cao' khi địa danh rõ và còn tồn tại; 'vừa' khi "
            "đã đổi tên/chỉ định vị tới cấp tỉnh-huyện; 'thấp' khi áng chừng vùng bao "
            "quanh HOẶC không định vị được (khi đó lat=lon=0.0)."
        )
    )
    admin_level: str = Field(
        description=(
            "Cấp hành chính phỏng đoán: 'quốc gia' | 'vùng' | 'tỉnh' | 'huyện' | "
            "'xã' | 'di tích' | 'sông/núi' ... '' nếu không rõ. (Chỉ vào review.)"
        )
    )
    modern_name: str = Field(
        description=(
            "Tên hiện đại tương ứng nếu địa danh đã đổi tên (vd 'Gia Định' -> "
            "'TP. Hồ Chí Minh'). '' nếu trùng tên cũ hoặc không rõ. (Chỉ vào review.)"
        )
    )
    note: str = Field(
        description="Ghi chú ngắn lý do/độ mơ hồ. '' nếu không cần. (Chỉ vào review.)"
    )

class GeocodeOutcome(BaseModel):
    """Kết quả geocode đã HỢP NHẤT từ mọi nguồn (Google/LLM), đủ cho cả DB lẫn review.

    KHÁC `GeocodeResult` (response_format strict của LLM): đây là kiểu NỘI BỘ pipeline
    -> được phép default + Optional. `lat`/`lon` = None nghĩa là KHÔNG định vị được
    -> địa danh đó chỉ lên timeline, không marker.
    """

    lat: float | None = None
    lon: float | None = None
    confidence: Literal["cao", "vừa", "thấp"] = "thấp"
    resolved_by: Literal["google", "llm", "none"] = "none"
    provider_name: str = ""  # tên provider trả về (Google formatted_address / LLM modern_name) — review
    admin_level: str = ""  # review-only
    modern_name: str = ""  # review-only
    note: str = ""  # review-only
