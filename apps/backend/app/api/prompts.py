"""Quản lý Prompt router (admin) — prefix /api/admin/prompts. Item 2.

Sửa/version **system prompt tĩnh** đã seed từ code sang Postgres. Lưu là đẩy production ngay
(không có bản nháp staging); `promote` chỉ dùng để rollback về version cũ trong lịch sử. Agent
đọc version production lúc chạy (get_active_prompt) + luôn fallback về hằng code.
created_by/promoted_by lấy từ email admin đang đăng nhập (audit).
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.core.errors import AppError
from app.models import prompt as repo
from app.models.user import User
from app.schemas.prompt import (
    CreateVersionInput,
    PromptDetail,
    PromptListItem,
    PromptVersionContent,
    PromptVersionMeta,
)

router = APIRouter(dependencies=[Depends(require_admin)])

@router.get("", response_model=list[PromptListItem])
async def list_prompts() -> list[PromptListItem]:
    rows = await anyio.to_thread.run_sync(repo.list_prompts)
    return [PromptListItem(**r) for r in rows]

@router.get("/{key}", response_model=PromptDetail)
async def get_prompt(key: str) -> PromptDetail:
    row = await anyio.to_thread.run_sync(repo.get_prompt, key)
    if row is None:
        raise AppError(404, "not_found", "Không tìm thấy prompt.")
    return PromptDetail(**row)

@router.get("/{key}/versions/{version_no}", response_model=PromptVersionContent)
async def get_version(key: str, version_no: int) -> PromptVersionContent:
    row = await anyio.to_thread.run_sync(repo.get_version, key, version_no)
    if row is None:
        raise AppError(404, "not_found", "Không tìm thấy phiên bản prompt.")
    return PromptVersionContent(**row)

@router.post("/{key}/versions", response_model=PromptVersionMeta)
async def create_version(
    key: str, body: CreateVersionInput, user: User = Depends(require_admin)
) -> PromptVersionMeta:
    """Tạo version mới VÀ đẩy production ngay (production cũ -> archived).
    created_by = promoted_by = email admin."""
    row = await anyio.to_thread.run_sync(
        repo.create_version, key, body.content, body.note, user.email
    )
    if row is None:
        raise AppError(404, "not_found", "Không tìm thấy prompt để tạo phiên bản.")
    return PromptVersionMeta(**row)

@router.post("/{key}/versions/{version_no}/promote", response_model=PromptDetail)
async def promote_version(
    key: str, version_no: int, user: User = Depends(require_admin)
) -> PromptDetail:
    """Rollback: đưa 1 version cũ trở lại production (production hiện tại -> archived).
    promoted_by = email admin. Trả detail mới để FE cập nhật."""
    ok = await anyio.to_thread.run_sync(repo.promote, key, version_no, user.email)
    if not ok:
        raise AppError(404, "not_found", "Không tìm thấy phiên bản để đẩy lên production.")
    row = await anyio.to_thread.run_sync(repo.get_prompt, key)
    if row is None:
        raise AppError(404, "not_found", "Không tìm thấy prompt.")
    return PromptDetail(**row)
