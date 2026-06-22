"""Schema cho LLM trích "atomic event" dựng lớp timeline + map.

Dùng làm `response_format` cho OpenAI Structured Outputs (strict json_schema).
Như `EntityExtraction`/`GraphExtraction`: strict mode KHÔNG cho default => mọi
field bắt buộc, LLM phải trả đủ. Dùng chuỗi rỗng "" thay cho "không có" (strict
không cho `None`); khi ghi DB sẽ convert "" -> NULL.

Đơn vị: **1 AtomicEvent = 1 mốc thời gian + (các) địa điểm của mốc đó**. Một sự
kiện lớn nhiều mốc rời -> nhiều AtomicEvent cùng `parent_event` (gom ở reconcile).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AtomicEvent(BaseModel):
    """Một sự kiện đã ràng buộc đủ when–where–what, đủ để chấm 1 điểm timeline
    và (nếu có toạ độ) 1 marker map."""

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
            "Mốc bắt đầu, ISO rút gọn: 'YYYY' | 'YYYY-MM' | 'YYYY-MM-DD' "
            "(vd '1862', '1862-03', '1862-06-05'). Suy năm từ ngữ cảnh nếu câu chỉ "
            "ghi tháng/ngày nhưng năm đã rõ trước đó (anchor inheritance) — khi suy "
            "như vậy hãy hạ `confidence`. Để '' nếu đoạn không cho biết thời gian."
        )
    )
    time_end: str = Field(
        description=(
            "Mốc kết thúc nếu sự kiện là KHOẢNG kéo dài (vd chiến dịch), cùng định "
            "dạng ISO rút gọn. Để '' nếu là một thời điểm."
        )
    )
    locations: list[str] = Field(
        description=(
            "Địa danh gắn với mốc này (surface form, giữ nguyên như văn bản). "
            "Phần tử ĐẦU là địa điểm CHÍNH để chấm marker. Nhiều nơi cùng lúc -> "
            "liệt kê hết. Để [] (rỗng) nếu đoạn không nêu địa điểm."
        )
    )
    parent_event: str = Field(
        description=(
            "Tên sự kiện/chiến dịch LỚN bao trùm mốc này (vd 'Khởi nghĩa Trương "
            "Định', 'Chiến dịch Điện Biên Phủ') để gom các mốc rời về một nhóm. "
            "Để '' nếu sự kiện đứng rời, không thuộc chuỗi nào."
        )
    )
    confidence: Literal["cao", "vừa", "thấp"] = Field(
        description=(
            "Độ chắc chắn của (thời gian + diễn biến): 'cao' khi mốc ghi rõ trong "
            "đoạn; 'vừa'/'thấp' khi phải suy từ ngữ cảnh hoặc mốc mơ hồ. Render "
            "đậm/nhạt theo trường này."
        )
    )


class TimelineExtraction(BaseModel):
    """Kết quả trích cho một unit (đoạn gom theo heading). Rỗng nếu đoạn không có
    sự kiện có diễn biến cụ thể."""

    events: list[AtomicEvent]
