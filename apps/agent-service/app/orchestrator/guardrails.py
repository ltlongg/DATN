"""Guardrails hook — điểm cắm cho plan guardrails riêng.

Mỗi batch answer (cụm/câu hoàn chỉnh) đi qua hook NÀY TRƯỚC khi byte rời server, nhờ vậy
guardrails có cơ hội chặn nội dung xấu (token đã gửi qua SSE thì không rút lại được).

Plan này CHỈ dựng cơ chế — hook mặc định no-op (luôn pass). Plan guardrails thay
`check_batch` bằng luật thật.
"""

from __future__ import annotations


async def check_batch(batch: str) -> bool:
    """Trả True nếu batch được phép emit, False nếu bị chặn. Mặc định: luôn pass."""
    return True
