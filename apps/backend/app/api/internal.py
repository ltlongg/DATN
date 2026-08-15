"""Endpoint nội bộ cho agent-service (KHÔNG prefix /api/admin, KHÔNG require_admin/JWT).

Caller là agent-service — một service nội bộ, không phải admin user đăng nhập — nên xác thực
bằng shared secret `X-Internal-Key` (core/internal_auth.py) chứ KHÔNG bằng JWT: JWT nằm trong
tay user nên user tự gọi thẳng endpoint nội bộ được. Chiều ngược lại (backend -> agent-service
`/ask`, `/kb/*`) dùng cùng header, gửi từ services/agent_client.py.

Chỉ READ system_config qua GET /internal/config. PUT vẫn CHỈ ở /api/admin/config
(require_admin) — admin sửa config là hành vi của người, không phải của service.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends

from app.core.internal_auth import verify_internal_key
from app.models import config as repo
from app.schemas.config import SystemConfigResponse

# Gác ở cấp router -> route nội bộ thêm sau tự động được bảo vệ.
router = APIRouter(dependencies=[Depends(verify_internal_key)])

@router.get("/config", response_model=SystemConfigResponse)
async def get_internal_config() -> SystemConfigResponse:
    return await anyio.to_thread.run_sync(repo.get_config)
