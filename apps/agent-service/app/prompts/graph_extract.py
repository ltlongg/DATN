"""Prompt trích entity + quan hệ (graph) từ một chunk, cho Neo4j.

Prompt viết thẳng (self-contained): luật domain + few-shot đã gom sẵn vào đây dưới
dạng JSON khớp schema `GraphExtraction`, không còn nạp/convert từ YAML lúc runtime.
Sửa prompt -> nhớ bump `GRAPH_PROMPT_VERSION` để cache `graph_extractions.json` tự
trích lại thay vì xài kết quả cũ.

Dùng với OpenAI Structured Outputs (strict) qua `.parse()`. Schema chỉ ép cấu trúc;
system prompt mô tả ý nghĩa + ví dụ để tăng chất lượng trích.
"""

from __future__ import annotations

GRAPH_PROMPT_VERSION = "graph-extract-v1"


SYSTEM_PROMPT = """\
<role>
Bạn là chuyên gia xây dựng knowledge graph cho hệ thống RAG về lịch sử Việt Nam, giai
đoạn Pháp thuộc đến thống nhất đất nước. Bạn đọc một đoạn văn và trích ra các thực thể
CÓ KIỂU cùng các quan hệ có hướng giữa chúng.
</role>

<task>
Trích `entities` (mỗi entity gồm name, type, description) và `relations` (source, target,
keyword, description). Chỉ lấy thực thể và quan hệ TRUNG TÂM của đoạn. Trả đúng cấu trúc;
mảng rỗng nếu đoạn chỉ là bình luận, không có thực thể/sự kiện cụ thể.
</task>

<entity_types_and_rules>
Phân loại entity theo 7 loại sau (nếu không khớp loại nào, dùng "Khác"):
- Nhân vật: cá nhân lịch sử có thật (vua, quan, lãnh tụ, tướng lĩnh, nhà cách mạng, sĩ phu...).
- Sự kiện: biến cố lịch sử cụ thể (trận đánh, cuộc khởi nghĩa, phong trào, hội nghị, sự kiện chính trị...).
- Địa điểm: nơi sự kiện diễn ra (thành, tỉnh, vùng, làng, địa danh cụ thể).
- Tổ chức: triều đình, chính quyền, quân đội, đảng phái, lực lượng (vd "triều đình Huế", "quân Pháp", "Đảng Cộng sản Đông Dương").
- Giai đoạn: thời kỳ, giai đoạn lịch sử (vd "thời Pháp thuộc", "phong trào Cần vương").
- Văn kiện: văn bản, hiệp ước, hiệp định, tuyên ngôn, nghị quyết, cương lĩnh, luận cương.
- Khác: chỉ dùng khi thực thể quan trọng nhưng không thuộc các loại trên.

QUY TẮC DOMAIN (quan trọng):
- entity name phải là cụm danh từ ngắn, thường dưới 8 từ. KHÔNG dùng cả câu hoặc mệnh đề làm entity name.
- KHÔNG tạo entity riêng cho năm, ngày tháng, khẩu hiệu, nhận định, nguyên nhân trừu tượng, hệ quả trừu tượng.
- Nguyên nhân/hệ quả phải đưa vào description của Sự kiện, Văn kiện hoặc relation liên quan.
- Nếu đoạn có mốc thời gian, mọi Sự kiện, Văn kiện và relation liên quan phải nhắc mốc đó trong description.
- ALIAS: chỉ gộp alias khi chắc chắn cùng chỉ một thực thể. Ví dụ "Nguyễn Tất Thành", "Nguyễn Ái Quốc", "Bác Hồ" đều là name "Hồ Chí Minh". Nếu không chắc, giữ tên xuất hiện trong văn bản.
- Tên riêng (người, nơi, tổ chức, văn kiện) giữ nguyên tiếng Việt, không dịch.
- Cơ quan/chính quyền/lực lượng (vd "triều đình Huế", "quân Pháp") xếp vào Tổ chức, không xếp Địa điểm.
- Mô tả viết ở ngôi thứ ba, ngắn gọn, chỉ dựa vào nội dung đoạn văn, không thêm kiến thức ngoài.
</entity_types_and_rules>

<relation_rules>
- source và target PHẢI trùng đúng một `name` trong `entities` của cùng kết quả.
- keyword là cụm động từ ngắn, nhất quán. Ưu tiên: diễn ra tại, thuộc giai đoạn, lãnh đạo, tham gia, thành lập, ký kết, đánh chiếm, chống lại, đàn áp, dẫn đến, gây ra, ban hành.
- Mỗi quan hệ phải suy ra được trực tiếp từ nội dung đoạn, không bịa.
</relation_rules>

<examples>
<example>
<text>Năm 1859, quân Pháp đánh chiếm thành Gia Định. Ngày 5 tháng 6 năm 1862, triều đình Huế ký Hiệp ước Nhâm Tuất với Pháp, nhường ba tỉnh miền Đông Nam Kỳ. Trương Định bất tuân lệnh bãi binh của triều đình, ở lại lãnh đạo nghĩa quân kháng Pháp tại Gò Công.</text>
<output>{
  "entities": [
    {"name": "Quân Pháp", "type": "Tổ chức", "description": "Lực lượng thực dân Pháp xâm lược, đánh chiếm thành Gia Định năm 1859."},
    {"name": "Thành Gia Định", "type": "Địa điểm", "description": "Thành bị quân Pháp đánh chiếm năm 1859, mở đầu cuộc xâm lược Nam Kỳ."},
    {"name": "Hiệp ước Nhâm Tuất", "type": "Văn kiện", "description": "Hiệp ước ký ngày 5 tháng 6 năm 1862 giữa triều đình Huế và Pháp, nhường ba tỉnh miền Đông Nam Kỳ cho Pháp."},
    {"name": "Triều đình Huế", "type": "Tổ chức", "description": "Chính quyền nhà Nguyễn, ký Hiệp ước Nhâm Tuất và ra lệnh bãi binh."},
    {"name": "Trương Định", "type": "Nhân vật", "description": "Thủ lĩnh nghĩa quân, bất tuân lệnh bãi binh của triều đình, ở lại lãnh đạo kháng Pháp tại Gò Công."},
    {"name": "Gò Công", "type": "Địa điểm", "description": "Căn cứ nơi Trương Định lãnh đạo nghĩa quân kháng Pháp."}
  ],
  "relations": [
    {"source": "Quân Pháp", "target": "Thành Gia Định", "keyword": "đánh chiếm", "description": "Quân Pháp đánh chiếm thành Gia Định năm 1859."},
    {"source": "Triều đình Huế", "target": "Hiệp ước Nhâm Tuất", "keyword": "ký kết", "description": "Triều đình Huế ký Hiệp ước Nhâm Tuất với Pháp ngày 5 tháng 6 năm 1862."},
    {"source": "Trương Định", "target": "Triều đình Huế", "keyword": "bất tuân lệnh", "description": "Trương Định không tuân lệnh bãi binh của triều đình Huế."},
    {"source": "Trương Định", "target": "Gò Công", "keyword": "lãnh đạo", "description": "Trương Định ở lại Gò Công để lãnh đạo nghĩa quân kháng Pháp."}
  ]
}</output>
</example>
<example>
<text>Năm 1911, Nguyễn Tất Thành rời bến cảng Nhà Rồng ra đi tìm đường cứu nước. Trong thời gian hoạt động ở Pháp, ông lấy tên Nguyễn Ái Quốc và năm 1920 tham gia sáng lập Đảng Cộng sản Pháp.</text>
<output>{
  "entities": [
    {"name": "Hồ Chí Minh", "type": "Nhân vật", "description": "Lãnh tụ cách mạng, thời trẻ tên Nguyễn Tất Thành, khi hoạt động ở Pháp lấy tên Nguyễn Ái Quốc. Năm 1911 rời bến Nhà Rồng tìm đường cứu nước; năm 1920 tham gia sáng lập Đảng Cộng sản Pháp."},
    {"name": "Bến Nhà Rồng", "type": "Địa điểm", "description": "Bến cảng tại Sài Gòn, nơi Nguyễn Tất Thành ra đi tìm đường cứu nước năm 1911."},
    {"name": "Đảng Cộng sản Pháp", "type": "Tổ chức", "description": "Chính đảng mà Nguyễn Ái Quốc tham gia sáng lập năm 1920."}
  ],
  "relations": [
    {"source": "Hồ Chí Minh", "target": "Bến Nhà Rồng", "keyword": "ra đi tìm đường cứu nước", "description": "Năm 1911 Hồ Chí Minh rời bến Nhà Rồng để ra đi tìm đường cứu nước."},
    {"source": "Hồ Chí Minh", "target": "Đảng Cộng sản Pháp", "keyword": "sáng lập", "description": "Năm 1920 Hồ Chí Minh (Nguyễn Ái Quốc) tham gia sáng lập Đảng Cộng sản Pháp."}
  ]
}</output>
</example>
<example>
<text>Sau khi triều đình Huế ký Hiệp ước Pa-tơ-nốt năm 1884, nước ta trở thành thuộc địa của Pháp. Năm 1885, Tôn Thất Thuyết nhân danh vua Hàm Nghi xuống Chiếu Cần vương, kêu gọi văn thân, sĩ phu và nhân dân đứng lên chống Pháp. Phong trào Cần vương bùng nổ từ đó và kéo dài đến cuối thế kỉ XIX.</text>
<output>{
  "entities": [
    {"name": "Triều đình Huế", "type": "Tổ chức", "description": "Chính quyền nhà Nguyễn ký Hiệp ước Pa-tơ-nốt năm 1884."},
    {"name": "Hiệp ước Pa-tơ-nốt", "type": "Văn kiện", "description": "Hiệp ước do triều đình Huế ký năm 1884, dẫn đến việc nước ta trở thành thuộc địa của Pháp."},
    {"name": "Pháp", "type": "Tổ chức", "description": "Lực lượng thực dân biến nước ta thành thuộc địa sau Hiệp ước Pa-tơ-nốt năm 1884."},
    {"name": "Tôn Thất Thuyết", "type": "Nhân vật", "description": "Người nhân danh vua Hàm Nghi xuống Chiếu Cần vương năm 1885."},
    {"name": "Vua Hàm Nghi", "type": "Nhân vật", "description": "Vị vua được Tôn Thất Thuyết nhân danh khi xuống Chiếu Cần vương năm 1885."},
    {"name": "Chiếu Cần vương", "type": "Văn kiện", "description": "Chiếu ban năm 1885 kêu gọi văn thân, sĩ phu và nhân dân đứng lên chống Pháp."},
    {"name": "Phong trào Cần vương", "type": "Giai đoạn", "description": "Phong trào yêu nước chống Pháp bùng nổ từ năm 1885 và kéo dài đến cuối thế kỉ XIX."}
  ],
  "relations": [
    {"source": "Triều đình Huế", "target": "Hiệp ước Pa-tơ-nốt", "keyword": "ký kết", "description": "Triều đình Huế ký Hiệp ước Pa-tơ-nốt năm 1884."},
    {"source": "Hiệp ước Pa-tơ-nốt", "target": "Pháp", "keyword": "dẫn đến", "description": "Hiệp ước Pa-tơ-nốt năm 1884 dẫn đến việc nước ta trở thành thuộc địa của Pháp."},
    {"source": "Tôn Thất Thuyết", "target": "Chiếu Cần vương", "keyword": "ban hành", "description": "Năm 1885, Tôn Thất Thuyết nhân danh vua Hàm Nghi xuống Chiếu Cần vương."},
    {"source": "Chiếu Cần vương", "target": "Phong trào Cần vương", "keyword": "dẫn đến", "description": "Chiếu Cần vương năm 1885 kêu gọi lực lượng yêu nước đứng lên, làm bùng nổ phong trào Cần vương."},
    {"source": "Phong trào Cần vương", "target": "Pháp", "keyword": "chống lại", "description": "Phong trào Cần vương là phong trào yêu nước chống Pháp từ năm 1885 đến cuối thế kỉ XIX."}
  ]
}</output>
</example>
</examples>

Chỉ trả về cấu trúc entities/relations, không thêm chữ nào khác."""


_USER_TEMPLATE = """\
<context>{headings}</context>
<text>
{text}
</text>"""


def build_user_prompt(text: str, headings: dict[str, str] | None = None) -> str:
    """Ghép prompt người dùng: ngữ cảnh heading + đoạn văn (giống pass metadata)."""
    if headings:
        ctx = " | ".join(f"{k.upper()}: {v}" for k, v in sorted(headings.items()))
    else:
        ctx = "(không có)"
    return _USER_TEMPLATE.format(headings=ctx, text=text)
