"""Cấu hình hệ thống router (admin) — prefix /api/admin/config.

GET đọc dòng singleton; PUT cập nhật một phần (exclude_unset). Áp dụng LIVE cho agent-service
qua endpoint nội bộ GET /internal/config (xem api/internal.py) — độ trễ tối đa = TTL cache
runtime_config của agent-service (~60s). Xem docs/plan/system-config-plan.md.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.models import config as repo
from app.schemas.config import SystemConfigResponse, SystemConfigUpdate

router = APIRouter(dependencies=[Depends(require_admin)])


@router.get("", response_model=SystemConfigResponse)
async def get_system_config() -> SystemConfigResponse:
    return await anyio.to_thread.run_sync(repo.get_config)


@router.put("", response_model=SystemConfigResponse)
async def update_system_config(body: SystemConfigUpdate) -> SystemConfigResponse:
    fields = body.model_dump(exclude_unset=True)
    return await anyio.to_thread.run_sync(repo.update_config, fields)
