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

class GuardrailDecision(BaseModel):
    """Kết quả kiểm 1 input. `action="block"` -> emit safe_message + blocked, dừng flow."""

    action: Literal["allow", "block"]
    # Nhóm vi phạm khi block (rỗng khi allow). Nhiều nhóm nếu input dính nhiều loại.
    categories: list[GuardrailCategory] = Field(default_factory=list)
    # Câu trả lời an toàn stream cho người dùng khi block (tiếng Việt, lịch sự, không lộ
    # chi tiết luật). Rỗng khi allow.
    safe_message: str = ""
