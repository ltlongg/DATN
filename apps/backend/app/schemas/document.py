"""Schema cho admin documents (danh mục tài liệu nguồn)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DocumentStatus = Literal["draft", "indexing", "indexed", "failed"]

class DocumentCreate(BaseModel):
    # KHÔNG có `source_file`: tài liệu có nguồn trong kho TỰ hiện ở danh mục
    # (models/document.py::sync_kb_documents). Form chỉ tạo được tài liệu chưa gắn nguồn.
    name: str = Field(min_length=1, max_length=300)
    type: str = Field(default="markdown", max_length=50)
    status: DocumentStatus = "draft"

class DocumentUpdate(BaseModel):
    # PATCH: chỉ field được gửi mới cập nhật (exclude_unset ở API). KHÔNG có `source_file`
    # (khóa nối, immutable — xem models/document.py::UPDATABLE_COLS) và KHÔNG có
    # `chunk_count` (đếm thật từ kho, không phải số nhập vào).
    name: str | None = Field(default=None, min_length=1, max_length=300)
    type: str | None = Field(default=None, max_length=50)
    status: DocumentStatus | None = None

class DocumentOut(BaseModel):
    id: str
    name: str
    type: str
    status: DocumentStatus
    source_file: str | None = None
    chunk_count: int
    event_count: int
    created_at: datetime
    updated_at: datetime

class KbSourceOut(BaseModel):
    """Nguồn có thật trong kho tri thức — dùng cho dropdown lọc ở KB Chunks."""

    source_file: str
    chunk_count: int
    event_count: int
    document_id: str | None = None
