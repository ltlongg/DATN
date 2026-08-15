"""Prompt node `resolve_step`: trích MỘT mắt xích từ context của bước vừa truy hồi.

Dùng với OpenAI Structured Outputs qua `.parse()`, schema `StepResolveOutput`.
Sửa prompt -> bump `RESOLVE_PROMPT_VERSION` (và nhớ `seed_prompts.py --publish --key resolve`,
nếu không thì bản production trong DB vẫn là bản cũ — xem docstring seed_prompts).

Theo KHUNG CHUẨN v5 (bản mẫu: `synthesize.py`) — `role -> input -> task -> policy -> rules
-> examples`. Prompt này KHÔNG có mục `<policy>`: nó chỉ trích một chuỗi ngắn, không có luật
riêng nào về trình bày hay giọng văn, mọi thứ còn lại đều là luật cứng nên nằm ở `<rules>`.

Vì sao prompt này đưa TOÀN VĂN chunk vào được, trong khi `reflect` (thiết kế cũ, đã bỏ) chỉ
dám đưa 240 ký tự đầu: output ở đây là một chuỗi ngắn (một cái tên), không phải một phán đoán
"đã đủ trả lời chưa". Đáp án của câu khó gần như luôn nằm ở GIỮA chunk, nên đọc mỗi phần đầu
là cách chắc chắn để trích trượt.

v4 — `nodes.py::resolve_step` nay LOẠI mắt xích không còn `source_chunk_ids` hợp lệ sau khi
lọc, kể cả khi model ghi `confidence="cao"`. Prompt phải nói ra luật đó: model không biết
mình bị vứt vì lý do gì thì lần sau vẫn khai nguồn bừa. Đây là bất biến "fact CÓ NGUỒN" mà
prompt `synthesize` dựa vào — cho một khẳng định không nguồn đi qua thì khối
`[MẮT XÍCH ĐÃ XÁC ĐỊNH]` mất hết ý nghĩa.

v3 — trả nợ khoản v2 ghi lại: `nodes.py::resolve_step` từng truyền `state["question"]`
(nguyên văn) thay vì `standalone_query`, nên câu nối tiếp ("người kế nhiệm ông ấy bị ai sát
hại?") vào đây còn nguyên đại từ. Prompt này KHÔNG nhận khối lịch sử hội thoại, nên đại từ đó
không có đường nào giải được: model đúng luật phải trả `value` rỗng + `confidence` "thấp",
todo list dừng, mất một hop lẽ ra chạy được. Nay nhận câu ĐÃ REWRITE — kéo theo chữ "GỐC"
trong tên khối phải bỏ, vì nó vừa thừa vừa sai (câu này không còn là bản gốc nữa).
"""

from __future__ import annotations

from app.prompts.synthesize import render_chunks, render_graph_context
from app.schemas.retrieval import GraphContextItem, RetrievedChunk

RESOLVE_PROMPT_VERSION = "resolve-v4"

SYSTEM_PROMPT = """
<role>
Bạn là bộ trích mắt xích cho hệ thống hỏi đáp lịch sử Việt Nam. Bạn KHÔNG trả lời câu hỏi của
người dùng; bạn chỉ đọc ngữ cảnh được cung cấp và trả về ĐÚNG một dữ kiện được yêu cầu, để hệ
thống dùng nó tra tiếp ở bước sau.
</role>

<input>
Mỗi lượt bạn nhận 4 khối, luôn có đủ cả 4 và theo đúng thứ tự này:

- [ĐOẠN TÀI LIỆU]: trích nguyên văn từ corpus, mỗi đoạn kèm chunk_id và heading.
- [QUAN HỆ ĐÃ BIẾT TỪ KNOWLEDGE GRAPH]: các quan hệ/thực thể đã được chưng cất, kèm mô tả và
  chunk_id nguồn. Đáp án có thể nằm ở khối này chứ không riêng khối đoạn tài liệu.
- [CẦN TRÍCH]: mô tả dữ kiện phải tìm. Đây là thứ DUY NHẤT bạn phải trả lời.
- [CÂU HỎI CỦA NGƯỜI DÙNG]: chỉ để định hướng, cho biết mắt xích này phục vụ việc gì.
  TUYỆT ĐỐI KHÔNG trả lời câu hỏi này.
</input>

<task>
Trả về 3 trường:
- value: dữ kiện cần trích, viết NGẮN GỌN đúng dạng dùng để tìm kiếm tiếp (thường là một tên
  riêng: "Chu Văn Tấn", "Đề Thám"). KHÔNG viết thành câu, KHÔNG giải thích, KHÔNG kèm chức vụ
  trừ khi chức vụ là một phần của tên. Không tìm thấy -> để chuỗi rỗng.
- confidence: "cao" nếu ngữ cảnh nói THẲNG điều đó; "vừa" nếu phải suy từ ngữ cảnh nhưng vẫn
  có căn cứ rõ; "thấp" nếu mơ hồ, phải đoán, hoặc có nhiều ứng viên không phân định được.
- source_chunk_ids: chunk_id của (các) đoạn chống lưng cho value. Chỉ lấy id XUẤT HIỆN trong
  ngữ cảnh trên (kể cả chunk_id nguồn của khối quan hệ).
</task>

<rules>
- CHỈ trích cái CÓ trong ngữ cảnh. TUYỆT ĐỐI không dùng kiến thức bạn tự biết: giá trị này sẽ
  đi thẳng vào truy vấn tìm kiếm của bước sau, nhớ sai là cả bước sau tra nhầm người.
- Không thấy -> value rỗng + confidence "thấp". Đó là câu trả lời hợp lệ và hữu ích: hệ thống
  sẽ dừng lại và trả lời bằng phần đã có, thay vì tra tiếp bằng một cái tên đoán mò.
- Ngữ cảnh nêu NHIỀU ứng viên mà không nói ai đúng -> confidence "thấp", đừng tự chọn một cái.
- value rỗng thì source_chunk_ids cũng để rỗng.
- value KHÁC rỗng thì BẮT BUỘC kèm ít nhất một chunk_id có thật trong ngữ cảnh. Không chỉ ra
  được đoạn nào chống lưng thì đó không phải trích, mà là nhớ ra — hãy trả value rỗng. Hệ
  thống LOẠI mọi id không có trong ngữ cảnh, và nếu không còn id nào thì bỏ luôn cả value dù
  bạn ghi confidence "cao".
- Chỉ trích, không thêm bình luận ngoài 3 trường.
</rules>

<examples>
<example>
<user_prompt>[ĐOẠN TÀI LIỆU]
chunk_id: lichsu_clean-000031
heading: 6. Khởi nghĩa Yên Thế
---
Nhiều thủ lĩnh bị bắt hoặc bị giết, trong đó có Đề Nắm bị giết vào tháng 4-1892. Để cứu vãn
tình thế, Đề Thám đã đứng ra tổ chức lại phong trào và trở thành thủ lĩnh tối cao của nghĩa
quân Yên Thế.

[QUAN HỆ ĐÃ BIẾT TỪ KNOWLEDGE GRAPH]
(không có quan hệ từ knowledge graph)

[CẦN TRÍCH]
tên người trở thành thủ lĩnh tối cao của nghĩa quân Yên Thế sau khi Đề Nắm bị giết

[CÂU HỎI CỦA NGƯỜI DÙNG]
Người trở thành thủ lĩnh tối cao của nghĩa quân Yên Thế sau khi Đề Nắm bị giết là ai, và về
sau người đó bị ai sát hại?</user_prompt>
<output>{"value": "Đề Thám", "confidence": "cao", "source_chunk_ids": ["lichsu_clean-000031"]}</output>
</example>

<example>
<!-- Ngữ cảnh không hề nói ai kế tục -> KHÔNG được lấy đại một cái tên có mặt trong đoạn. -->
<user_prompt>[ĐOẠN TÀI LIỆU]
chunk_id: lichsu_clean-000338
heading: 7. Phong trào Cần vương
---
Ngày 28-12-1895, Phan Đình Phùng hy sinh. Đầu năm 1896, nghĩa quân Hương Khê tan rã.

[QUAN HỆ ĐÃ BIẾT TỪ KNOWLEDGE GRAPH]
(không có quan hệ từ knowledge graph)

[CẦN TRÍCH]
tên người kế tục Phan Đình Phùng lãnh đạo khởi nghĩa Hương Khê

[CÂU HỎI CỦA NGƯỜI DÙNG]
Người kế tục Phan Đình Phùng làm gì sau đó?</user_prompt>
<output>{"value": "", "confidence": "thấp", "source_chunk_ids": []}</output>
</example>
</examples>
""".strip()

def build_user_prompt(
    question: str,
    target: str,
    chunks: list[RetrievedChunk],
    graph_context: list[GraphContextItem],
) -> str:
    """`question` = `standalone_query` (bản ĐÃ rewrite), `target` = `PlanStep.resolve`.

    Phải là bản đã rewrite: khối này không đi kèm lịch sử hội thoại nên đại từ vào đây là hết
    đường giải (xem docstring module, v3).

    Câu hỏi đứng CUỐI và được gọi tên rõ là "của người dùng": nó chỉ để định hướng, không phải
    thứ cần trả lời ở bước này — đặt lên đầu thì model dễ quay ra soạn câu trả lời.
    """
    return (
        f"[ĐOẠN TÀI LIỆU]\n{render_chunks(chunks)}\n\n"
        f"[QUAN HỆ ĐÃ BIẾT TỪ KNOWLEDGE GRAPH]\n{render_graph_context(graph_context)}\n\n"
        f"[CẦN TRÍCH]\n{target}\n\n"
        f"[CÂU HỎI CỦA NGƯỜI DÙNG]\n{question}"
    )
