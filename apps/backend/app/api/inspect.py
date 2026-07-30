"""KB Inspector router (admin, read-only) — prefix /api/admin/kb.

Chunk + event query thẳng Postgres (psycopg). Entity ở Neo4j nên proxy sang agent-service
qua agent_client. Điều hướng chéo bằng `chunk_id` (xem backend-additions-plan.md §2.4).
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends, Query

from app.api.deps import require_admin
from app.core.errors import AppError
from app.models import inspect as repo
from app.schemas.inspect import (
    ChunkDetail,
    ChunkListItem,
    ChunkListResponse,
    EventDetail,
    EventListItem,
    EventListResponse,
    EventRef,
)
from app.services.agent_client import agent_get

# require_admin áp cho toàn router -> user thường gọi bất kỳ route nào đều nhận 403.
router = APIRouter(dependencies=[Depends(require_admin)])


# --- chunks (Postgres) ---


@router.get("/chunks", response_model=ChunkListResponse)
async def list_chunks(
    q: str | None = Query(default=None),
    heading: str | None = Query(default=None),
    source_file: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> ChunkListResponse:
    rows, total = await anyio.to_thread.run_sync(
        repo.list_chunks, q, heading, source_file, limit, offset
    )
    return ChunkListResponse(
        items=[ChunkListItem(**r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/chunks/{chunk_id}", response_model=ChunkDetail)
async def get_chunk(chunk_id: str) -> ChunkDetail:
    chunk = await anyio.to_thread.run_sync(repo.get_chunk, chunk_id)
    if chunk is None:
        raise AppError(404, "not_found", "Không tìm thấy chunk.")
    events = await anyio.to_thread.run_sync(repo.list_events_for_chunk, chunk_id)
    return ChunkDetail(
        chunk_id=chunk["chunk_id"],
        text=chunk["text"],
        metadata=chunk["metadata"] or {},
        heading_path=chunk["heading_path"] or [],
        referencing_events=[EventRef(**e) for e in events],
    )


# --- events (Postgres) ---


@router.get("/events", response_model=EventListResponse)
async def list_events(
    q: str | None = Query(default=None),
    confidence: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> EventListResponse:
    rows, total = await anyio.to_thread.run_sync(repo.list_events, q, confidence, limit, offset)
    return EventListResponse(
        items=[EventListItem(**r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/events/{event_id}", response_model=EventDetail)
async def get_event(event_id: str) -> EventDetail:
    event = await anyio.to_thread.run_sync(repo.get_event, event_id)
    if event is None:
        raise AppError(404, "not_found", "Không tìm thấy sự kiện.")
    return EventDetail(**event)


# --- entities (proxy Neo4j qua agent-service) ---


@router.get("/entities")
async def list_entities(
    q: str | None = Query(default=None),
    type: str | None = Query(default=None),
    chunk_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> object:
    return await agent_get(
        "/kb/entities",
        {"q": q, "type": type, "chunk_id": chunk_id, "limit": limit, "offset": offset},
    )


@router.get("/entities/{norm_name}")
async def get_entity(norm_name: str) -> object:
    return await agent_get(f"/kb/entities/{norm_name}")
