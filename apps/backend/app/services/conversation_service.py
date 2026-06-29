"""Logic thuần (không I/O) cho conversation: đặt title + dựng bounded history.

Tách thuần để unit-test không cần DB. DB access nằm ở models/conversation.py; API layer
ghép hai phần qua anyio.to_thread.
"""

from __future__ import annotations

from app.models.conversation import Message

DEFAULT_TITLE = "Cuộc trò chuyện mới"
_TITLE_MAX_CHARS = 80


def derive_title(question: str) -> str:
    """Title từ câu hỏi đầu: gộp khoảng trắng/xuống dòng, cắt ~80 ký tự. Không gọi LLM."""
    flat = " ".join(question.split())
    if not flat:
        return DEFAULT_TITLE
    if len(flat) <= _TITLE_MAX_CHARS:
        return flat
    return flat[:_TITLE_MAX_CHARS].rstrip() + "…"


def build_bounded_history(
    messages: list[Message], max_messages: int, *, max_chars: int = 4000
) -> list[dict[str, str]]:
    """Map message DB -> history cho agent-service (role/content), áp đúng ràng buộc của
    `AskRequest.history` (mỗi item 1..4000 ký tự, tối đa `max_messages` item gần nhất).

    Quy tắc (backend-plan.md "Conversation Handling"):
    - chỉ role user/assistant (mọi message của ta đều thuộc 2 loại này);
    - bỏ assistant content rỗng (lỗi kỹ thuật) — clarification có content nên vẫn giữ;
    - cắt content > max_chars để agent không trả 422;
    - giữ thứ tự thời gian, lấy `max_messages` cái cuối.
    """
    history: list[dict[str, str]] = []
    for msg in messages:  # messages đã sort created_at ASC từ list_messages
        if msg.role not in ("user", "assistant"):
            continue
        content = msg.content.strip()
        if not content:
            continue  # assistant rỗng = lỗi kỹ thuật, bỏ
        if len(content) > max_chars:
            content = content[:max_chars]
        history.append({"role": msg.role, "content": content})
    if max_messages >= 0:
        history = history[-max_messages:] if max_messages else []
    return history
