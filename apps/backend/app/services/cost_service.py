"""Logic thuần (không I/O) tổng hợp chi phí từ usage rows. Tách thuần để unit-test không
cần DB (cùng idiom quality_service.py). Input rỗng -> tổng hợp rỗng (0 lượt / mảng rỗng),
dùng cho cả case 'chưa có usage' lẫn 'bảng llm_usage chưa tồn tại'. Xem
backend-additions-plan.md §4.2.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.schemas.cost import CostOverview, DailyCost, TaskCost


def _day_key(created_at: Any) -> str:
    """created_at (datetime hoặc str) -> 'YYYY-MM-DD'."""
    if hasattr(created_at, "date"):
        return created_at.date().isoformat()
    return str(created_at)[:10]


def compute_cost_overview(rows: list[dict[str, Any]]) -> CostOverview:
    total_calls = len(rows)
    total_tokens = sum(int(r.get("total_tokens") or 0) for r in rows)
    total_prompt = sum(int(r.get("prompt_tokens") or 0) for r in rows)
    total_completion = sum(int(r.get("completion_tokens") or 0) for r in rows)
    avg = (total_tokens / total_calls) if total_calls else 0.0
    return CostOverview(
        total_calls=total_calls,
        total_tokens=total_tokens,
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        avg_tokens_per_call=round(avg, 2),
    )


def compute_cost_by_day(rows: list[dict[str, Any]]) -> list[DailyCost]:
    """Group theo ngày (created_at::date), sort tăng dần — cho biểu đồ theo ngày."""
    calls: dict[str, int] = defaultdict(int)
    tokens: dict[str, int] = defaultdict(int)
    for r in rows:
        day = _day_key(r.get("created_at"))
        calls[day] += 1
        tokens[day] += int(r.get("total_tokens") or 0)
    return [
        DailyCost(day=day, calls=calls[day], total_tokens=tokens[day])
        for day in sorted(calls)
    ]


def compute_cost_by_task(rows: list[dict[str, Any]]) -> list[TaskCost]:
    """Group theo task ('plan' | 'synthesize' | ...), sort theo task."""
    calls: dict[str, int] = defaultdict(int)
    tokens: dict[str, int] = defaultdict(int)
    for r in rows:
        task = str(r.get("task") or "unknown")
        calls[task] += 1
        tokens[task] += int(r.get("total_tokens") or 0)
    return [
        TaskCost(task=task, calls=calls[task], total_tokens=tokens[task])
        for task in sorted(calls)
    ]
