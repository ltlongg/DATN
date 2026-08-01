"""Khối user prompt dùng chung cho các node online nhận "lịch sử + câu hỏi hiện tại".

`plan` và `guardrails_input` trước đây chép Y HỆT `_render_history` + `build_user_prompt`
(hai bản 100% giống nhau, ở hai file). Chép đôi thì sớm muộn cũng sửa lệch một bên — mà lệch
ở đây nghĩa là guardrails đọc lịch sử hội thoại theo một định dạng, plan đọc theo định dạng
khác, trong khi cả hai đang bàn về đúng một câu hỏi.

Nhãn khối dùng `[NGOẶC VUÔNG]` chứ không phải thẻ XML tiếng Việt (`<câu_hỏi_hiện_tại>` như
bản cũ): system prompt đã dùng thẻ XML cho các mục cấu trúc (`<role>`, `<task>`...), để user
prompt cũng dùng thẻ thì hai tầng lẫn vào nhau — nhìn vào một thẻ không biết nó là khung
prompt hay là dữ liệu. Nhân tiện, thẻ có dấu tiếng Việt cũng bị tokenizer chia vụn.
"""

from __future__ import annotations

from app.schemas.ask import ChatMessage

HISTORY_LABEL = "[LỊCH SỬ HỘI THOẠI]"
QUESTION_LABEL = "[CÂU HỎI HIỆN TẠI]"


def render_history(history: list[ChatMessage]) -> str:
    """Lịch sử hội thoại -> text. Rỗng -> "(không có)" chứ không phải chuỗi rỗng: khối trống
    trơn dễ bị đọc là dữ liệu bị mất, còn "(không có)" nói rõ đây là lượt đầu."""
    if not history:
        return "(không có)"
    return "\n".join(
        f"{'Người dùng' if msg.role == 'user' else 'Trợ lý'}: {msg.content}"
        for msg in history
    )


def build_history_question_prompt(question: str, history: list[ChatMessage]) -> str:
    """User prompt chuẩn cho node chỉ cần lịch sử + câu hỏi (plan, guardrails_input)."""
    return (
        f"{HISTORY_LABEL}\n{render_history(history)}\n\n"
        f"{QUESTION_LABEL}\n{question}"
    )
