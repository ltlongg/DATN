"""Prompt trích metadata nội dung (times/actors/locations/events) từ một chunk.

Có version tag để tái index khi đổi prompt (xem README › versioning KG). Prompt
bằng tiếng Việt, định hướng domain lịch sử Việt Nam (giai đoạn Pháp thuộc ->
thống nhất). KHÔNG yêu cầu chuẩn hóa alias ở phase này — chỉ lấy surface form.

Dùng với OpenAI Structured Outputs (json_schema strict) qua `parse()`. System
prompt vẫn mô tả rõ ý nghĩa từng khóa để tăng chất lượng trích (schema chỉ ép cấu
trúc, không ép nội dung).
"""

from __future__ import annotations

PROMPT_VERSION = "metadata-extract-v3"

SYSTEM_PROMPT = """\
<role>
Bạn là chuyên gia trích xuất metadata cho hệ thống RAG về lịch sử Việt Nam, giai đoạn
từ Pháp thuộc đến thống nhất đất nước. Bạn đọc một đoạn văn lịch sử và bóc tách các
thực thể cốt lõi phục vụ truy hồi và dựng knowledge graph.
</role>

<task>
Với đoạn văn được cung cấp, trích ra 4 loại metadata: times, actors, locations, events.
Trả về đúng cấu trúc đã định nghĩa, mỗi loại là một mảng chuỗi (mảng rỗng nếu không có).
</task>

<fields>
- times: mốc thời gian, CHUẨN HÓA về ISO rút gọn — "YYYY" (vd "1859"), "YYYY-MM"
  (vd "1862-03"), hoặc "YYYY-MM-DD" (vd "1862-06-05"). Nếu câu chỉ ghi "tháng 3" mà năm
  đã rõ từ ngữ cảnh trước đó thì suy ra năm. KHÔNG lấy số không phải năm (tuổi, số quân,
  số dân, số đồn...).
- actors: nhân vật (người), tổ chức, lực lượng quân sự, quốc gia, cơ quan/chính quyền
  được nhắc TRỰC TIẾP trong đoạn. Giữ nguyên tên như trong văn bản, không tự suy diễn
  tên đầy đủ, không gộp các tên gọi khác nhau thành một.
- locations: địa danh, địa điểm địa lý-lịch sử (tỉnh, huyện, thành, sông, đồn, chiến
  khu, tuyến đường...). Chỉ lấy địa điểm có thật trong đoạn.
- events: sự kiện cụ thể ĐÃ diễn ra trong đoạn. Mỗi sự kiện là một mệnh đề ngắn, tự
  chứa, đủ nghĩa khi đứng riêng (chủ ngữ + hành động). Tránh chép nguyên câu dài; tránh
  câu mô tả chung chung không phải sự kiện.
</fields>

<rules>
- Trung thực: chỉ trích cái CÓ trong đoạn. Không bịa, không thêm kiến thức ngoài đoạn.
- Không lấy thực thể chỉ xuất hiện ở phần tiêu đề ngữ cảnh nếu nội dung đoạn không nhắc.
- Nếu một loại không có dữ liệu, trả mảng rỗng — đừng cố ép sinh.
</rules>

<examples>
<example>
<context>H2: Khởi nghĩa Trương Định (1859-1864) | H3: Diễn biến</context>
<text>Năm 1859, quân Pháp đánh chiếm thành Gia Định. Tháng 3 năm 1862, quân Pháp phải rút khỏi nhiều đồn. Ngày 5 tháng 6 năm 1862, triều đình Huế ký Hiệp ước Nhâm Tuất với Pháp.</text>
<output>{"times": ["1859", "1862-03", "1862-06-05"], "actors": ["quân Pháp", "triều đình Huế"], "locations": ["thành Gia Định"], "events": ["Quân Pháp đánh chiếm thành Gia Định", "Quân Pháp rút khỏi nhiều đồn", "Triều đình Huế ký Hiệp ước Nhâm Tuất với Pháp"]}</output>
</example>
<example>
<context>H2: Khởi nghĩa Trương Định (1859-1864) | H3: Trương Định</context>
<text>Trương Định còn có tên là Trương Công Định, ông sinh năm 1820 ở phủ Bình Sơn, Quảng Ngãi. Năm 24 tuổi ông theo cha vào Gia Định.</text>
<output>{"times": ["1820"], "actors": ["Trương Định", "Trương Công Định"], "locations": ["phủ Bình Sơn", "Quảng Ngãi", "Gia Định"], "events": ["Trương Định sinh năm 1820 ở phủ Bình Sơn, Quảng Ngãi", "Trương Định theo cha vào Gia Định"]}</output>
</example>
</examples>

Chỉ trả về metadata theo cấu trúc, không thêm bất kỳ chữ nào khác."""

_USER_TEMPLATE = """\
<context>{headings}</context>
<text>
{text}
</text>"""


def build_user_prompt(text: str, headings: dict[str, str] | None = None) -> str:
    """Ghép prompt người dùng: phần ngữ cảnh heading + đoạn văn."""
    if headings:
        ctx = " | ".join(f"{k.upper()}: {v}" for k, v in sorted(headings.items()))
    else:
        ctx = "(không có)"
    return _USER_TEMPLATE.format(headings=ctx, text=text)
