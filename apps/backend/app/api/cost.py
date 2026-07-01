"""Module 4 — Chi phí router (admin) — prefix /api/admin/cost.

Đọc thẳng bảng llm_usage (cùng Postgres) rồi tổng hợp bằng hàm thuần. Bảng chưa tồn tại ->
models trả [] -> endpoint trả 200 với số liệu rỗng (KHÔNG 500). Xem backend-additions-plan §4.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin
from app.models import cost as repo
from app.schemas.cost import CostOverview, DailyCost, TaskCost, TopUserCost
from app.services.cost_service import (
    compute_cost_by_day,
    compute_cost_by_task,
    compute_cost_overview,
)

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("/overview", response_model=CostOverview)
async def overview(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
) -> CostOverview:
    rows = await anyio.to_thread.run_sync(repo.list_usage_rows, from_date, to_date)
    return compute_cost_overview(rows)


@router.get("/by-day", response_model=list[DailyCost])
async def by_day(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
) -> list[DailyCost]:
    rows = await anyio.to_thread.run_sync(repo.list_usage_rows, from_date, to_date)
    return compute_cost_by_day(rows)


@router.get("/by-task", response_model=list[TaskCost])
async def by_task(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
) -> list[TaskCost]:
    rows = await anyio.to_thread.run_sync(repo.list_usage_rows, from_date, to_date)
    return compute_cost_by_task(rows)


@router.get("/top-users", response_model=list[TopUserCost])
async def top_users(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=100),
) -> list[TopUserCost]:
    rows = await anyio.to_thread.run_sync(
        repo.list_top_users, from_date, to_date, limit
    )
    return [TopUserCost(**r) for r in rows]
