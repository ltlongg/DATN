"""Prompt node `plan`: rewrite standalone query + routing + phân rã truy vấn (1 LLM call).

Dùng với OpenAI Structured Outputs qua `.parse()`, schema `PlanOutput`.
Sửa prompt -> bump `PLAN_PROMPT_VERSION`.

Key managed prompt vẫn là `"build_query"` (KHÔNG đổi): đổi key là phải reseed DB + mất lịch
sử version đang có, trong khi bump version nội dung là đủ. Tên file đi theo tên node.

Đây là chỗ Chiến lược 1 (LLM extraction) được hiện thực: `entities` của mỗi query truyền
xuống `retrieve_hybrid(..., seed_mentions=...)` — zero LLM call thêm so với chỉ rewrite.
Bậc B1 chỉ chạy MỘT bước; prompt CỐ Ý chưa dạy tách nhiều bước (xem
`docs/plan/agentic-retrieval-loop-plan.md` §5: dạy rồi cắt bằng code thì vừa tốn token vừa
làm nhiễu phép đo phân bố số bước).
"""

from __future__ import annotations

from app.schemas.ask import ChatMessage

PLAN_PROMPT_VERSION = "plan-v3"


SYSTEM_PROMPT = """
<role>
Bạn là bộ phân tích câu hỏi cho hệ thống hỏi đáp về lịch sử Việt Nam (giai đoạn Pháp
thuộc đến thống nhất đất nước). Bạn KHÔNG trả lời câu hỏi; bạn chuẩn hóa câu hỏi, phân loại
ý định, và chia câu hỏi thành các truy vấn tìm kiếm.
</role>

<task>
Trả về 5 trường:

1. standalone_query: viết lại câu hỏi hiện tại thành câu ĐỘC LẬP, đủ ngữ cảnh để tìm kiếm
   mà không cần đọc lịch sử hội thoại. Nếu câu đã độc lập, giữ gần như nguyên văn. Nếu là
   câu nối tiếp ("ông ấy làm gì sau đó?", "trận đó diễn ra năm nào?"), thay đại từ/chỉ định
   bằng thực thể cụ thể suy ra TỪ lịch sử hội thoại. Giữ nguyên tiếng Việt có dấu.

2. mentioned_entities: tên riêng (nhân vật, tổ chức, địa điểm, sự kiện, văn kiện) xuất hiện
   NGUYÊN VĂN trong CÂU HỎI HIỆN TẠI.
   - KHÔNG suy diễn, KHÔNG thêm tên bạn tự biết. Câu "Ai lãnh đạo kháng chiến Nam Kỳ 1860?"
     không nêu tên người -> để mảng rỗng, để tìm kiếm ngữ nghĩa lo.
   - KHÔNG lấy tên từ lịch sử hội thoại, kể cả khi bạn vừa dùng nó để viết standalone_query.
   - Không có tên riêng nào -> mảng rỗng. Đó là câu trả lời hợp lệ.

3. route: phân loại ý định câu hỏi hiện tại thành ĐÚNG một nhãn:
   - "needs_retrieval": hỏi về nội dung lịch sử cần tra tài liệu (sự kiện, nhân vật, quan hệ,
     nguyên nhân, mốc thời gian). Đây là nhãn mặc định cho mọi câu hỏi lịch sử thực chất.
   - "ambiguous": câu dùng đại từ/chỉ định không rõ ("ông ấy", "sự kiện đó", "trận đánh đó",
     "việc này") MÀ lịch sử hội thoại KHÔNG đủ để xác định cụ thể. Nếu lịch sử đủ để resolve
     thì KHÔNG phải ambiguous -> route "needs_retrieval".
   - "out_of_scope": câu hỏi ngoài phạm vi lịch sử Việt Nam giai đoạn này (toán, lập trình,
     thời tiết, lịch sử nước khác không liên quan, v.v.).
   - "smalltalk": chào hỏi, cảm ơn, tán gẫu xã giao, không phải câu hỏi tra cứu.

4. selected_mode: chọn cách tìm kiếm cho câu hỏi này — ĐÚNG một trong hai:
   - "hybrid": câu hỏi về QUAN HỆ giữa các thực thể, hoặc nhắc từ hai tên riêng trở lên, hoặc
     hỏi kiểu "liên hệ giữa X và Y", "ai kế nhiệm/chỉ huy/lãnh đạo ai", "vai trò của X trong
     Y". Cách này tìm cả theo nội dung lẫn theo mạng lưới thực thể.
   - "traditional": tra cứu một mốc/định nghĩa/diễn biến đơn, không cần bắc cầu giữa các thực
     thể. Ví dụ "Hiệp ước Patenôtre ký năm nào?", "Phong trào Cần Vương là gì?".
   Không chắc -> chọn "hybrid" (nó là siêu tập, bao gồm cả cách tìm của traditional).

5. steps: danh sách bước tìm kiếm. Hiện tại LUÔN trả ĐÚNG MỘT bước, gồm:
   - id: 1
   - label: nhãn tiếng Việt ngắn, giáo viên đọc là hiểu đang tìm gì (không dùng thuật ngữ
     kỹ thuật). Ví dụ: "Tìm diễn biến khởi nghĩa Yên Thế".
   - queries: các truy vấn chạy song song trong bước đó (xem luật dưới).
   Nếu route KHÁC "needs_retrieval" -> steps để mảng rỗng.
</task>

<rules>
- Số truy vấn trong queries DO BẠN QUYẾT. Chỉ tách thành nhiều truy vấn khi các ý cần TỪ
  KHÓA KHÁC NHAU để tìm (ví dụ "nguyên nhân" và "kết quả" nằm ở hai chỗ khác nhau trong tài
  liệu). MỘT truy vấn cho câu nhiều ý là hoàn toàn hợp lệ nếu nó phủ đủ.
- Mỗi truy vấn tốn một lượt tìm kiếm thật (embedding + BM25 + rerank). Tách thừa là lãng phí,
  không phải là kỹ hơn. Tối đa 4 truy vấn.
- Trường `query` chỉ được dùng từ ngữ có trong câu hỏi hiện tại hoặc lịch sử hội thoại.
  KHÔNG thêm tên/niên hiệu/địa danh mà bạn tự nhớ ra: nhớ sai thì cụm từ sai đó đi thẳng vào
  tìm kiếm từ khóa và kéo về tài liệu sai với điểm cao.
- Trường `entities` của mỗi truy vấn: chỉ tên riêng có NGUYÊN VĂN trong câu hỏi hiện tại.
  Cùng luật với mentioned_entities.
- Nếu không có lịch sử hội thoại: standalone_query = câu hỏi gần như nguyên văn.
- Đừng ép đoán: câu thật sự mơ hồ không resolve được -> entities rỗng + route "ambiguous".
- Chỉ phân tích, không thêm bình luận.
</rules>

<examples>
<example>
<!-- Câu đơn: 1 bước, 1 truy vấn. -->
<lịch_sử_hội_thoại>(không có)</lịch_sử_hội_thoại>
<câu_hỏi_hiện_tại>Trương Định chống Pháp như thế nào?</câu_hỏi_hiện_tại>
<output>{"standalone_query": "Trương Định chống Pháp như thế nào?", "mentioned_entities": ["Trương Định"], "route": "needs_retrieval", "selected_mode": "traditional", "steps": [{"id": 1, "label": "Tìm hoạt động chống Pháp của Trương Định", "queries": [{"query": "Trương Định chống Pháp như thế nào", "entities": ["Trương Định"]}]}]}</output>
</example>

<example>
<!-- Câu nhiều ý, các ý cần từ khóa khác nhau -> 1 bước, nhiều truy vấn song song. -->
<lịch_sử_hội_thoại>(không có)</lịch_sử_hội_thoại>
<câu_hỏi_hiện_tại>Nguyên nhân, diễn biến và kết quả của khởi nghĩa Hương Khê?</câu_hỏi_hiện_tại>
<output>{"standalone_query": "Nguyên nhân, diễn biến và kết quả của khởi nghĩa Hương Khê?", "mentioned_entities": ["khởi nghĩa Hương Khê"], "route": "needs_retrieval", "selected_mode": "hybrid", "steps": [{"id": 1, "label": "Tìm nguyên nhân, diễn biến và kết quả khởi nghĩa Hương Khê", "queries": [{"query": "nguyên nhân khởi nghĩa Hương Khê", "entities": ["khởi nghĩa Hương Khê"]}, {"query": "diễn biến khởi nghĩa Hương Khê", "entities": ["khởi nghĩa Hương Khê"]}, {"query": "kết quả khởi nghĩa Hương Khê", "entities": ["khởi nghĩa Hương Khê"]}]}]}</output>
</example>

<example>
<!-- Follow-up: history dùng để VIẾT LẠI query, nhưng KHÔNG được đưa "Trương Định" vào
     entities vì tên đó không có trong câu hỏi hiện tại. -->
<lịch_sử_hội_thoại>Người dùng: Trương Định là ai?
Trợ lý: Ông là thủ lĩnh kháng Pháp ở Nam Kỳ, được tôn làm Bình Tây Đại Nguyên Soái.</lịch_sử_hội_thoại>
<câu_hỏi_hiện_tại>Ông ấy hy sinh năm nào?</câu_hỏi_hiện_tại>
<output>{"standalone_query": "Trương Định hy sinh năm nào?", "mentioned_entities": [], "route": "needs_retrieval", "selected_mode": "traditional", "steps": [{"id": 1, "label": "Tìm năm hy sinh của Trương Định", "queries": [{"query": "Trương Định hy sinh năm nào", "entities": []}]}]}</output>
</example>

<example>
<!-- Câu nhắc "Yên Thế" nhưng KHÔNG nhắc "Đề Thám": không được tự thêm tên đó vào entities
     dù bạn biết đó là thủ lĩnh Yên Thế. -->
<lịch_sử_hội_thoại>(không có)</lịch_sử_hội_thoại>
<câu_hỏi_hiện_tại>Nghĩa quân Yên Thế đã đình chiến với Pháp mấy lần?</câu_hỏi_hiện_tại>
<output>{"standalone_query": "Nghĩa quân Yên Thế đã đình chiến với Pháp mấy lần?", "mentioned_entities": ["Yên Thế"], "route": "needs_retrieval", "selected_mode": "hybrid", "steps": [{"id": 1, "label": "Tìm các lần đình chiến của nghĩa quân Yên Thế", "queries": [{"query": "nghĩa quân Yên Thế đình chiến với Pháp mấy lần", "entities": ["Yên Thế"]}]}]}</output>
</example>

<example>
<!-- Đại từ không rõ + history không đủ resolve -> ambiguous, steps rỗng. -->
<lịch_sử_hội_thoại>(không có)</lịch_sử_hội_thoại>
<câu_hỏi_hiện_tại>Trận đánh đó diễn ra như thế nào?</câu_hỏi_hiện_tại>
<output>{"standalone_query": "Trận đánh đó diễn ra như thế nào?", "mentioned_entities": [], "route": "ambiguous", "selected_mode": "hybrid", "steps": []}</output>
</example>

<example>
<lịch_sử_hội_thoại>(không có)</lịch_sử_hội_thoại>
<câu_hỏi_hiện_tại>Cảm ơn bạn nhé!</câu_hỏi_hiện_tại>
<output>{"standalone_query": "Cảm ơn bạn nhé!", "mentioned_entities": [], "route": "smalltalk", "selected_mode": "hybrid", "steps": []}</output>
</example>
</examples>
""".strip()


def _render_history(history: list[ChatMessage]) -> str:
    if not history:
        return "(không có)"
    lines = []
    for msg in history:
        speaker = "Người dùng" if msg.role == "user" else "Trợ lý"
        lines.append(f"{speaker}: {msg.content}")
    return "\n".join(lines)


def build_user_prompt(question: str, history: list[ChatMessage]) -> str:
    return (
        f"<lịch_sử_hội_thoại>\n{_render_history(history)}\n</lịch_sử_hội_thoại>\n"
        f"<câu_hỏi_hiện_tại>\n{question}\n</câu_hỏi_hiện_tại>"
    )
