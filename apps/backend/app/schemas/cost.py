"""Schema cho Module 4 — Chi phí (cost dashboard, admin).

Chỉ track token của 2 lệnh gọi LLM online (build_query, synthesize). Ước tính $ là
CLIENT-SIDE (admin tự nhập giá/1K token trên UI), KHÔNG persist. Xem
backend-additions-plan.md §4.
"""

from __future__ import annotations

from pydantic import BaseModel


class CostOverview(BaseModel):
    total_calls: int
    total_tokens: int
    total_prompt_tokens: int
    total_completion_tokens: int
    avg_tokens_per_call: float


class DailyCost(BaseModel):
    day: str  # YYYY-MM-DD
    calls: int
    total_tokens: int


class TaskCost(BaseModel):
    task: str  # 'build_query' | 'synthesize'
    calls: int
    total_tokens: int


class TopUserCost(BaseModel):
    user_id: str
    email: str
    name: str
    total_tokens: int
    call_count: int
