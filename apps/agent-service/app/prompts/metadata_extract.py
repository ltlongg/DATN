"""Prompt trích metadata nội dung (times/actors/locations/events) từ một chunk.

Có version tag để tái index khi đổi prompt (xem README › versioning KG). Prompt
bằng tiếng Việt, định hướng domain lịch sử Việt Nam (giai đoạn Pháp thuộc ->
thống nhất). KHÔNG yêu cầu chuẩn hóa alias ở phase này — chỉ lấy surface form.

Dùng với OpenAI Structured Outputs (json_schema strict) qua `parse()`. System
prompt vẫn mô tả rõ ý nghĩa từng khóa để tăng chất lượng trích (schema chỉ ép cấu
trúc, không ép nội dung).
"""

from __future__ import annotations

PROMPT_VERSION = "metadata-extract-v5"

SYSTEM_PROMPT = """
<role>
Bạn là chuyên gia trích xuất metadata cho hệ thống RAG về lịch sử Việt Nam, giai đoạn
từ Pháp thuộc đến thống nhất đất nước. Bạn đọc một đoạn văn lịch sử và bóc tách các
thực thể CỐT LÕI phục vụ truy hồi và dựng knowledge graph.
</role>

<task>
Với đoạn văn được cung cấp, trích ra 4 loại metadata: times, actors, locations, events.
Chỉ lấy thực thể TRUNG TÂM của đoạn — những gì đoạn văn TẬP TRUNG nói đến, không phải
mọi thứ được nhắc thoáng qua. Trả về đúng cấu trúc đã định nghĩa, mỗi loại là mảng
chuỗi (mảng rỗng nếu không có).
</task>

<fields>
- times: tối đa 5 mốc thời gian QUAN TRỌNG NHẤT của đoạn. Chuẩn hóa ISO rút gọn —
  "YYYY", "YYYY-MM", "YYYY-MM-DD". Nếu câu chỉ ghi "tháng 3" mà năm đã rõ từ các câu
  trước trong cùng <text> thì suy; nếu không rõ thì không suy. KHÔNG suy năm từ heading.
  KHÔNG lấy số không phải năm (tuổi, số quân, số dân, số đồn...).
- actors: tối đa 5 nhân vật, tổ chức, lực lượng TRUNG TÂM — chủ thể hoặc đối tượng của
  hành động chính trong đoạn. Không lấy nhân vật chỉ được nhắc thoáng qua hoặc làm bối
  cảnh. Giữ nguyên tên như trong văn bản. Cơ quan/chính quyền/lực lượng (vd "triều đình
  Huế", "quân Pháp") đưa vào actors, không đưa vào locations.
- locations: tối đa 5 địa danh NƠI SỰ KIỆN CHÍNH DIỄN RA. Không lấy địa danh chỉ xuất
  hiện để mô tả xuất thân, bối cảnh phụ, hoặc liệt kê hàng loạt không gắn với hành động
  cụ thể. Không lấy cơ quan/lực lượng.
- events: 2-4 sự kiện QUAN TRỌNG NHẤT đã diễn ra trong đoạn. Mỗi sự kiện là mệnh đề
  ngắn, tự chứa (chủ ngữ + hành động). Tránh chép nguyên câu dài; tránh mô tả chung
  chung không phải sự kiện cụ thể. Được phép thay đại từ (vd "ông", "họ") bằng chủ thể
  đã rõ trong <text>.
</fields>

<rules>
- Trung thực: chỉ trích cái CÓ trong đoạn. Không bịa, không thêm kiến thức ngoài đoạn.
- Đoạn liệt kê nhiều nhân vật/địa điểm → chỉ lấy những cái đoạn VĂN TẬP TRUNG vào;
  bỏ qua những cái chỉ nhắc một lần thoáng qua hoặc chỉ là bối cảnh phụ.
- Không lấy thực thể chỉ xuất hiện ở phần tiêu đề ngữ cảnh nếu nội dung đoạn không nhắc.
- Không lặp chuỗi trùng nhau trong cùng một mảng; giữ thứ tự xuất hiện trong <text>.
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
<example>
<context>H2: Phong trào Cần vương | H3: Các cuộc khởi nghĩa</context>
<text>Tiêu biểu nhất trong phong trào Cần vương là khởi nghĩa Bãi Sậy do Nguyễn Thiện Thuật lãnh đạo tại vùng Hưng Yên, Hải Dương. Ngoài ra còn có nhiều cuộc khởi nghĩa nhỏ lẻ ở các tỉnh Thái Bình, Nam Định, Ninh Bình, Thanh Hóa, Nghệ An, Hà Tĩnh do nhiều văn thân sĩ phu địa phương khởi xướng nhưng nhanh chóng bị dập tắt.</text>
<output>{"times": [], "actors": ["Nguyễn Thiện Thuật"], "locations": ["Hưng Yên", "Hải Dương"], "events": ["Nguyễn Thiện Thuật lãnh đạo khởi nghĩa Bãi Sậy tại vùng Hưng Yên, Hải Dương"]}</output>
</example>
<example>
<context>H2: Khởi nghĩa Trương Định (1859-1864) | H3: Ý nghĩa lịch sử</context>
<text>Nhìn chung, cuộc khởi nghĩa tuy thất bại nhưng đã để lại nhiều bài học quý báu, thể hiện tinh thần bất khuất của một thời kỳ đầy biến động. Đây là đoạn bình luận, không thuật lại sự kiện cụ thể nào.</text>
<output>{"times": [], "actors": [], "locations": [], "events": []}</output>
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
