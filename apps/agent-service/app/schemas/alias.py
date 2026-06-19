"""Schema verdict cho LLM trọng tài alias (tầng 2b khử trùng entity).

Dùng làm `response_format` cho OpenAI Structured Outputs (strict json_schema) trong
`scripts/build_alias_map.py`. Strict mode KHÔNG cho default => mọi field bắt buộc.
Prompt mô tả ý nghĩa từng field: app/prompts/alias_judge.py.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class AliasVerdict(BaseModel):
    same: bool = Field(description="Hai thực thể có phải CÙNG MỘT đối tượng thực tế không.")
    canonical: str = Field(description="Tên chuẩn nên giữ — PHẢI là một trong hai tên đưa vào.")
    confidence: Literal["cao", "vừa", "thấp"] = Field(description="Độ tin của phán đoán same.")
    reason: str = Field(description="Lý do ngắn gọn (1 câu).")
