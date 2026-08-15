"""Schema cho LLM extraction metadata nội dung (times/actors/locations/events).

Dùng làm `response_format` cho OpenAI Structured Outputs (strict json_schema).
LƯU Ý: strict mode KHÔNG cho phép default value trong schema, nên mọi field ở đây
là bắt buộc và không gán default — LLM phải luôn trả đủ 4 mảng (rỗng nếu không có).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

class EntityExtraction(BaseModel):
    """Kết quả LLM trích từ một chunk. Giữ nguyên dạng bề mặt (surface form),
    chưa chuẩn hóa alias — canonical để phase sau (xem plan › Alias Và Chuẩn Hóa)."""

    times: list[str] = Field(
        description=(
            "Mốc thời gian trong đoạn, CHUẨN HÓA về ISO rút gọn: 'YYYY' (vd '1859'), "
            "'YYYY-MM' (vd '1862-03'), hoặc 'YYYY-MM-DD' (vd '1862-06-05'). Suy ra "
            "năm từ ngữ cảnh nếu câu chỉ ghi 'tháng 3' nhưng năm đã rõ trước đó. "
            "KHÔNG lấy số không phải năm (tuổi, số quân, số dân). Rỗng nếu không có."
        )
    )
    actors: list[str] = Field(
        description=(
            "Nhân vật, tổ chức, lực lượng, quốc gia hoặc cơ quan được nhắc trong "
            "đoạn. Giữ nguyên tên như trong văn bản (vd 'Trương Định', 'quân Pháp', "
            "'triều đình Huế'). Rỗng nếu không có."
        )
    )
    locations: list[str] = Field(
        description=(
            "Địa danh/địa điểm lịch sử-địa lý được nhắc (vd 'Gia Định', 'Gò Công', "
            "'sông Vàm Cỏ Đông'). Rỗng nếu không có."
        )
    )
    events: list[str] = Field(
        description=(
            "Sự kiện cụ thể, viết thành mệnh đề ngắn gọn, tự chứa (vd 'Quân Pháp "
            "đánh chiếm thành Gia Định', 'Ký Hiệp ước Nhâm Tuất'). Chỉ lấy sự kiện "
            "thực sự diễn ra trong đoạn. Rỗng nếu không có."
        )
    )
