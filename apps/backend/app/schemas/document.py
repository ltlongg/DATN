"""Schema cho admin documents (mock metadata)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DocumentStatus = Literal["draft", "indexing", "indexed", "failed"]


class DocumentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    type: str = Field(default="markdown", max_length=50)
    status: DocumentStatus = "draft"
    chunk_count: int = Field(default=0, ge=0)


class DocumentUpdate(BaseModel):
    # PATCH: chỉ field được gửi mới cập nhật (exclude_unset ở API).
    name: str | None = Field(default=None, min_length=1, max_length=300)
    type: str | None = Field(default=None, max_length=50)
    status: DocumentStatus | None = None
    chunk_count: int | None = Field(default=None, ge=0)


class DocumentOut(BaseModel):
    id: str
    name: str
    type: str
    status: DocumentStatus
    chunk_count: int
    created_at: datetime
    updated_at: datetime
