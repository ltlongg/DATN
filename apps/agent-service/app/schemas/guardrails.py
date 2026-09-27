"""Schema cho guardrails input layer (v1).

`GuardrailDecision` vừa là structured-output schema của LLM guardrails, vừa là kiểu trả về
của `check_input`. Quyết định allow/block HOÀN TOÀN do LLM (không regex/keyword/blocklist).

Xem `docs/plan/guardrails-input-plan.md`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# Nhóm vi phạm guardrails có thể gắn cho 1 quyết định block. Chỉ để log/telemetry realtime,
# KHÔNG dùng để re-route flow. Danh sách phản ánh Policy Defaults trong plan.
GuardrailCategory = Literal[
    "prompt_injection",
    "harmful_instructions",
    "self_harm",
    "illegal_activity",
    "sexual_content",
    "hate_harassment",
    "privacy_secret",
    "other",
]

class GuardrailVerdict(BaseModel):
    """Structured-output schema LLM guardrails trả về."""

    action: Literal["allow", "block"]
    # Nhóm vi phạm khi block (rỗng khi allow). Nhiều nhóm nếu input dính nhiều loại.
    categories: list[GuardrailCategory] = Field(default_factory=list)
    # Câu trả lời an toàn stream cho người dùng khi block (tiếng Việt, lịch sự, không lộ
    # chi tiết luật). Rỗng khi allow.
    safe_message: str = ""

class GuardrailDecision(GuardrailVerdict):
    """Kết quả kiểm 1 input. `action="block"` -> emit safe_message + blocked, dừng flow.

    `system_error` nằm NGOÀI schema LLM (LLM không tự gắn được): True = chặn vì guardrails
    lỗi/timeout (fail-closed), KHÔNG phải vì nội dung câu hỏi -> backend không gắn cờ vi phạm.
    """

    system_error: bool = False
