"""Endpoint nội bộ cho agent-service (KHÔNG prefix /api/admin, KHÔNG require_admin/JWT).

Caller là agent-service — một service nội bộ, không phải admin user đăng nhập — nên chỉ READ
system_config qua GET /internal/config. Mirror đúng pattern gọi chiều backend->agent-service
đã có (services/agent_client.py gọi /ask cũng không auth, dựa vào 2 service cùng mạng nội
bộ). PUT vẫn CHỈ ở /api/admin/config (require_admin). Nếu triển khai ra mạng public cần siết
chặt hơn (shared-secret header) — NGOÀI phạm vi plan hiện tại, xem CLAUDE.md §Architecture.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter

from app.models import config as repo
from app.schemas.config import SystemConfigResponse

router = APIRouter()


@router.get("/config", response_model=SystemConfigResponse)
async def get_internal_config() -> SystemConfigResponse:
    return await anyio.to_thread.run_sync(repo.get_config)
