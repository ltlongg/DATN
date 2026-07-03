"""Lỗi nội bộ của orchestrator answer flow."""

from __future__ import annotations

from collections.abc import Sequence


class SynthesisError(RuntimeError):
    """LLM synthesize thất bại (refusal / rỗng / lỗi stream). `code` để map error event."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class GuardrailsBlocked(RuntimeError):
    """Guardrails chặn input -> dừng flow. Node guard_input đã emit `token(safe_message)` +
    `blocked` TRƯỚC khi raise; runner streaming chỉ cần dừng (không thêm error/done). Đường
    non-stream (`run_ask`) đọc `safe_message`/`categories` từ đây để dựng AskResponse.

    (Cũng dùng chung cho tình huống 1 batch answer bị chặn ở output guardrails sau này — các
    batch sạch đã emit giữ nguyên, không retract.)"""

    def __init__(
        self,
        reason: str = "guardrails",
        *,
        safe_message: str = "",
        categories: Sequence[str] | None = None,
    ) -> None:
        super().__init__(reason)
        self.reason = reason
        self.safe_message = safe_message
        self.categories: list[str] = list(categories or [])
