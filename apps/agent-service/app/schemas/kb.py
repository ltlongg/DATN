"""Schema response cho KB Inspector graph endpoints (agent-service /kb/*).

Read-only: list/paginate entity + ego-graph 1-hop. Backend proxy nguyên các response
này (xem backend-additions-plan.md §2.2/2.3).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class EntityListItem(BaseModel):
    name: str
    norm_name: str
    type: str | None = None
    description_count: int
    source_chunk_count: int


class EntityListResponse(BaseModel):
    items: list[EntityListItem]
    total: int
    limit: int
    offset: int


class EntityEdge(BaseModel):
    source_name: str | None = None
    source_norm: str | None = None
    target_name: str | None = None
    target_norm: str | None = None
    keyword: str | None = None
    description: str = ""
    source_chunk_ids: list[str] = Field(default_factory=list)


class EntityNeighbor(BaseModel):
    name: str | None = None
    norm_name: str | None = None
    type: str | None = None


class EntityDetail(BaseModel):
    name: str
    norm_name: str
    type: str | None = None
    descriptions: list[str] = Field(default_factory=list)
    source_chunk_ids: list[str] = Field(default_factory=list)
    neighbors: list[EntityNeighbor] = Field(default_factory=list)
    edges: list[EntityEdge] = Field(default_factory=list)
