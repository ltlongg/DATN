"""Quy tắc admin được thấy gì ở trang Hội thoại — hàm thuần, không DB.

- Người dùng bật chia sẻ -> thấy nội dung mọi message (vẫn ẩn danh tính).
- Câu hỏi bị guardrails gắn cờ vi phạm -> thấy câu đó + câu trả lời an toàn ngay sau nó.
- Còn lại -> chỉ số liệu: bỏ content, citations, visualization, steps (steps có câu hỏi đã
  viết lại, citations lộ chủ đề hỏi).
- Danh tính (email/tên) chỉ lộ khi hội thoại có ít nhất 1 tin bị gắn cờ.

Quyết định dựa trên trạng thái chia sẻ LÚC ĐỌC: người dùng tắt chia sẻ là admin mất quyền xem
cả hội thoại cũ.
"""

from __future__ import annotations

from typing import Any

from app.schemas.logs import Visibility

def message_visibility(messages: list[dict[str, Any]], shared: bool) -> list[Visibility]:
    """Visibility của từng message (cùng thứ tự `messages`, đã sắp theo thời gian)."""
    result: list[Visibility] = []
    prev_flagged = False
    for m in messages:
        if shared:
            result.append("shared")
        elif m["flagged"] or (m["role"] == "assistant" and prev_flagged):
            result.append("flagged")
        else:
            result.append("hidden")
        prev_flagged = bool(m["flagged"])
    return result

def redact_message(message: dict[str, Any]) -> dict[str, Any]:
    """Bản chỉ còn số liệu của 1 message."""
    return {
        **message,
        "content": None,
        "citations": [],
        "visualization": None,
        "steps": [],
    }

def reveal_identity(flagged_count: int) -> bool:
    return flagged_count > 0
