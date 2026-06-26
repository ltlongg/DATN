"""Schema cho LLM trích "atomic event" dựng lớp timeline + map.

Dùng làm `response_format` cho OpenAI Structured Outputs (strict json_schema).
Như `EntityExtraction`/`GraphExtraction`: strict mode KHÔNG cho default => mọi
field bắt buộc, LLM phải trả đủ. Dùng chuỗi rỗng "" thay cho "không có" (strict
không cho `None`); khi ghi DB sẽ convert "" -> NULL.

Đơn vị: **1 AtomicEvent = 1 diễn biến cụ thể + mốc thời gian + (các) địa điểm của
mốc đó**. Diễn biến là bắt buộc; thời gian/địa điểm ưu tiên đủ nhưng chấp nhận thiếu
một vế (thiếu thời gian -> chỉ map; thiếu địa điểm -> chỉ timeline). Một sự kiện lớn
nhiều mốc rời -> nhiều AtomicEvent cùng `parent_event` (gom ở reconcile).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Thang độ chắc chắn dùng chung cho timeline/map (đồng bộ với AliasVerdict).
Confidence = Literal["cao", "vừa", "thấp"]

# Thứ hạng confidence (cao > vừa > thấp). Một nguồn DUY NHẤT cho mọi nơi cần so sánh:
# reconcile (chọn bản chắc hơn khi gộp), builder (mắt xích yếu nhất khi render marker),
# build_gazetteer (sắp review). Đừng định nghĩa lại tại chỗ.
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
            "Mốc bắt đầu, ISO rút gọn: 'YYYY' | 'YYYY-MM' | 'YYYY-MM-DD' "
            "(vd '1862', '1862-03', '1862-06-05'). Suy năm từ ngữ cảnh nếu câu chỉ "
            "ghi tháng/ngày nhưng năm đã rõ trước đó (anchor inheritance) — khi suy "
            "như vậy hãy hạ `confidence`. Mốc mơ hồ ('đầu năm 1945', 'mùa thu') -> chỉ "
            "ghi mức chắc chắn ('1945'), KHÔNG bịa tháng/ngày. Để '' nếu đoạn không cho "
            "biết thời gian, hoặc chỉ có quan hệ trình tự ('sau đó', 'sau hiệp ước')."
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


class TimelineExtraction(BaseModel):
    """Kết quả trích cho một unit (đoạn gom theo heading). Rỗng nếu đoạn không có
    sự kiện có diễn biến cụ thể."""

    events: list[AtomicEvent]
