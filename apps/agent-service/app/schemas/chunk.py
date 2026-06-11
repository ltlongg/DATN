"""Pydantic models cho chunk — khớp schema trong `docs/plan/chunking-embedding-plan.md`.

Dùng để validate output trước khi ghi `chunks_llm.json`, đảm bảo mọi chunk có đủ
metadata nền. Metadata nội dung (events/actors/times/locations) cho phép rỗng ở phase
này.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ChunkMetadata(BaseModel):
    document_title: str
    headings: dict[str, str] = Field(default_factory=dict)

    # Metadata nội dung — phase đầu để rỗng, extract sau.
    events: list[str] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    times: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)

    # Truy vết / citation.
    source_file: str
    chunk_index: int
    start_line: int
    end_line: int
    start_index: int
    end_index: int

    # Thống kê token.
    text_token_count: int
    embedding_token_count: int


class Chunk(BaseModel):
    chunk_id: str
    text: str
    embedding_text: str
    metadata: ChunkMetadata
