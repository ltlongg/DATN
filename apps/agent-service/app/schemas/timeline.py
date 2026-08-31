"""Schema cho LLM trích "atomic event" dựng lớp timeline + map.

Dùng làm `response_format` cho OpenAI Structured Outputs (strict json_schema).
Như `EntityExtraction`/`GraphExtraction`: strict mode KHÔNG cho default => mọi
field bắt buộc, LLM phải trả đủ. Dùng chuỗi rỗng "" thay cho "không có" (strict
không cho `None`); khi ghi DB sẽ convert "" -> NULL.

Đơn vị: **1 AtomicEvent = 1 diễn biến cụ thể + mốc thời gian + (các) địa điểm của
mốc đó**. Diễn biến là bắt buộc; thời gian/địa điểm ưu tiên đủ nhưng chấp nhận thiếu
một vế (thiếu thời gian -> chỉ map; thiếu địa điểm -> chỉ timeline). Một sự kiện lớn
nhiều mốc rời -> nhiều AtomicEvent cùng `parent_event` (gom ở reconcile).

Kết quả trả về theo TỪNG CHUNK (`chunk_results`), không phải một danh sách phẳng cho
cả unit: LLM đọc trọn unit để có ngữ cảnh nhưng phải quy mỗi event về đúng chunk chứa
bằng chứng -> provenance ở cấp chunk, UI chỉ hiện timeline của chunk thực sự được dùng.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Thang độ chắc chắn dùng chung cho timeline/map (đồng bộ với AliasVerdict).
Confidence = Literal["cao", "vừa", "thấp"]

# Thứ hạng confidence (cao > vừa > thấp), dùng khi reconcile chọn bản chắc hơn.
CONFIDENCE_RANK: dict[str, int] = {"cao": 3, "vừa": 2, "thấp": 1}


class AtomicEvent(BaseModel):
    """Một diễn biến cụ thể (when–where–what), đủ để chấm 1 điểm timeline và (nếu có
    toạ độ) 1 marker map. Chấp nhận thiếu thời gian (chỉ map) hoặc địa điểm (chỉ timeline)."""

    label: str = Field(
        description=(
            "Tên sự kiện NGẮN, tự chứa (vd 'Ký Hiệp ước Nhâm Tuất', 'Quân Pháp "
            "đánh chiếm thành Gia Định'). Không viết cả đoạn."
        )
    )
    summary: str = Field(
        description=(
            "1–2 câu mô tả diễn biến, dùng làm tooltip. Chỉ dựa vào nội dung đoạn, "
            "không bịa."
        )
    )
    time_start: str = Field(
        description=(
            "Mốc bắt đầu lịch sử: năm/tháng/ngày SCN dùng '40' | '1010-07' | "
            "'1954-05-07'; TCN dùng '179 TCN' | '179-03 TCN'; chỉ biết thế kỷ "
            "dùng số La Mã như 'XII' hoặc 'III TCN'. Giữ đúng độ chi tiết nguồn, "
            "không đổi thế kỷ thành năm đại diện. Để '' nếu không có mốc độc lập."
        )
    )
    time_end: str = Field(
        description=(
            "Mốc kết thúc nếu sự kiện là khoảng kéo dài, dùng cùng quy ước với "
            "time_start. Để '' nếu sự kiện là một thời điểm."
        )
    )
    locations: list[str] = Field(
        description=(
            "Địa danh gắn với mốc này (surface form, giữ nguyên như văn bản), theo "
            "đúng THỨ TỰ XUẤT HIỆN trong văn bản. Phần tử ĐẦU là marker chính + khóa "
            "định danh event -> chỉ đảo lên đầu khi văn bản nói rõ nơi sự kiện diễn ra "
            "chủ yếu. Nhiều nơi cùng lúc -> liệt kê hết. [] nếu đoạn không nêu địa điểm."
        )
    )
    parent_event: str = Field(
        description=(
            "Tên sự kiện/chiến dịch LỚN bao trùm mốc này (vd 'Khởi nghĩa Trương "
            "Định', 'Chiến dịch Điện Biên Phủ') để gom các mốc rời về một nhóm. "
            "Để '' nếu sự kiện đứng rời, không thuộc chuỗi nào."
        )
    )
    confidence: Confidence = Field(
        description=(
            "Độ chắc chắn của (thời gian + diễn biến): 'cao' khi mốc ghi rõ trong "
            "đoạn; 'vừa'/'thấp' khi phải suy từ ngữ cảnh hoặc mốc mơ hồ. Render "
            "đậm/nhạt theo trường này."
        )
    )


class ChunkEvents(BaseModel):
    """Sự kiện trích được TỪ MỘT chunk trong unit (khớp marker `ref` của prompt)."""

    chunk_ref: str = Field(
        description=(
            "Đúng giá trị `ref` của thẻ <chunk> chứa bằng chứng cho các event bên "
            "dưới (vd '1', '2'). KHÔNG tự đặt ref mới."
        )
    )
    events: list[AtomicEvent] = Field(
        description=(
            "Các event mà chunk này làm bằng chứng. `[]` nếu chunk không có diễn "
            "biến nào đáng lên timeline (hợp lệ, không phải lỗi)."
        )
    )


class TimelineExtraction(BaseModel):
    """Kết quả trích cho một unit: mỗi chunk đầu vào ĐÚNG MỘT phần tử `chunk_results`.

    Thiếu/trùng/lạ `chunk_ref` -> extractor loại cả unit và trích lại (không nhận
    kết quả một phần, vì cache ghi theo chunk nên phần thiếu sẽ âm thầm mất event).
    """

    chunk_results: list[ChunkEvents]
