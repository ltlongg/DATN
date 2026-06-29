"""Gom event SSE của agent-service để tái dựng assistant message lưu DB.

Thuần (không I/O) -> unit-test dễ. Vừa proxy event xuống frontend, endpoint vừa feed
từng event vào collector này; kết thúc stream thì lấy `message_fields()` để lưu (xem
backend-plan.md "SSE Persistence Strategy"). Message lưu DB khớp đúng nội dung frontend
đã thấy.
"""

from __future__ import annotations

from typing import Any


class SseCollector:
    def __init__(self) -> None:
        self._tokens: list[str] = []
        self.citations: list[dict[str, Any]] = []
        self.visualization: dict[str, Any] | None = None
        self.clarification_needed: bool = False
        self.clarification_question: str | None = None
        self.confidence: str | None = None
        self.retrieval_mode: str = "none"
        self.warnings: list[Any] = []
        self.blocked: bool = False
        self.error: dict[str, Any] | None = None

    @property
    def content(self) -> str:
        return "".join(self._tokens)

    def feed(self, event: str, data: dict[str, Any]) -> None:
        if event == "token":
            self._tokens.append(str(data.get("text", "")))
        elif event == "citations":
            self.citations = list(data.get("citations") or [])
        elif event == "visualization":
            viz = data.get("visualization")
            self.visualization = viz if isinstance(viz, dict) else None
        elif event == "clarification":
            self.clarification_needed = True
            self.clarification_question = str(data.get("question") or "")
        elif event == "regenerating":
            # Agent bỏ lượt synthesize cũ, soạn lại -> xóa token đã gom để khớp frontend.
            self._tokens = []
        elif event == "blocked":
            self.blocked = True
        elif event == "error":
            self.error = {
                "code": str(data.get("code", "error")),
                "message": str(data.get("message", "")),
            }
        elif event == "done":
            self.confidence = data.get("confidence")  # có thể None
            self.retrieval_mode = str(data.get("retrieval_mode", "none"))
            self.warnings = list(data.get("warnings") or [])

    def should_persist(self) -> bool:
        """Có lưu assistant message không.

        - error/blocked -> KHÔNG lưu (frontend đã thấy lỗi qua SSE; assistant rỗng sẽ bị
          loại khỏi history nên lưu cũng vô nghĩa).
        - clarification -> lưu (cần trong history cho lượt sau).
        - câu trả lời thường -> lưu nếu có nội dung.
        """
        if self.error is not None or self.blocked:
            return False
        if self.clarification_needed:
            return True
        return bool(self.content.strip())

    def message_fields(self) -> dict[str, Any]:
        """kwargs cho models.conversation.add_message (chỉ gọi khi should_persist())."""
        if self.clarification_needed:
            return {
                "role": "assistant",
                "content": self.clarification_question or "",
                "clarification_needed": True,
                "retrieval_mode": "none",
            }
        return {
            "role": "assistant",
            "content": self.content,
            "clarification_needed": False,
            "citations": self.citations,
            "visualization": self.visualization,
            "retrieval_mode": self.retrieval_mode,
            "confidence": self.confidence,
            "warnings": self.warnings,
        }
