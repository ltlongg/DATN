"""Schema cho KB Inspector (read-only). Chunk/event query thẳng Postgres; entity proxy
từ agent-service nên forward nguyên JSON (không khai schema chặt ở backend)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class EventRef(BaseModel):
    """Event tham chiếu một chunk (panel 'được tham chiếu bởi')."""

    event_id: str
    label: str
    time_start: str | None = None
    time_end: str | None = None
    confidence: str


class ChunkListItem(BaseModel):
    chunk_id: str
    heading_path: list[str] = Field(default_factory=list)
    source_file: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    preview: str


class ChunkListResponse(BaseModel):
    items: list[ChunkListItem]
    total: int
    limit: int
    offset: int


class ChunkDetail(BaseModel):
    chunk_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    heading_path: list[str] = Field(default_factory=list)
    # Event tham chiếu chunk (Postgres). Entity tham chiếu lấy qua GET /kb/entities?chunk_id.
    referencing_events: list[EventRef] = Field(default_factory=list)


class EventListItem(BaseModel):
    event_id: str
    label: str
    time_start: str | None = None
    time_end: str | None = None
    locations: list[str] = Field(default_factory=list)
    confidence: str


class EventListResponse(BaseModel):
    items: list[EventListItem]
    total: int
    limit: int
    offset: int


class EventDetail(BaseModel):
    event_id: str
    label: str
    summary: str
    time_start: str | None = None
    time_end: str | None = None
    locations: list[str] = Field(default_factory=list)
    confidence: str
    parent_event_norm: str | None = None
    source_chunk_ids: list[str] = Field(default_factory=list)
