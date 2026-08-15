"""Schema cho quản lý Prompt (Item 2, admin). Mirror bảng managed_prompts / prompt_versions."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

class PromptListItem(BaseModel):
    key: str
    grp: str
    title: str
    description: str | None
    active_version_no: int | None  # None nếu chưa có version production
    version_count: int
    updated_at: datetime

class PromptVersionMeta(BaseModel):
    version_no: int
    note: str | None
    status: str  # 'production' | 'archived'
    created_by: str | None
    created_at: datetime
    promoted_by: str | None
    promoted_at: datetime | None

class PromptDetail(BaseModel):
    key: str
    grp: str
    title: str
    description: str | None
    updated_at: datetime
    production_content: str | None  # content đang chạy (None nếu chưa có production)
    versions: list[PromptVersionMeta]

class PromptVersionContent(BaseModel):
    version_no: int
    content: str
    status: str

class CreateVersionInput(BaseModel):
    content: str = Field(min_length=1)
    note: str | None = Field(default=None, max_length=500)
