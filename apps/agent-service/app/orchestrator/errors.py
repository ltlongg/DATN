"""Lỗi nội bộ của orchestrator answer flow."""

from __future__ import annotations


class SynthesisError(RuntimeError):
    """LLM synthesize thất bại (refusal / rỗng / lỗi stream). `code` để map error event."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class GuardrailsBlocked(RuntimeError):
    """Một batch answer bị guardrails hook chặn -> dừng stream. Các batch sạch trước đó
    đã emit thì giữ nguyên (không retract)."""

    def __init__(self, reason: str = "guardrails") -> None:
        super().__init__(reason)
        self.reason = reason
