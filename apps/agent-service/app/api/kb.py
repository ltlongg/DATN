"""Router /kb/* — read-only graph endpoints cho KB Inspector (backend proxy sang đây).

Neo4j driver là SYNC nên dùng endpoint `def` thường (FastAPI chạy trong threadpool),
không chặn event loop. Không có endpoint ghi/xóa — quản lý graph là việc sau.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.kb import EntityDetail, EntityListItem, EntityListResponse
from app.tools.graph_rag import graph_store

router = APIRouter(prefix="/kb", tags=["kb"])


@router.get("/entities", response_model=EntityListResponse)
def list_entities(
    q: str | None = Query(default=None),
    type: str | None = Query(default=None),
    chunk_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> EntityListResponse:
    rows = graph_store.list_entities(
        type=type, q=q, chunk_id=chunk_id, limit=limit, offset=offset
    )
    total = graph_store.count_entities(type=type, q=q, chunk_id=chunk_id)
    return EntityListResponse(
        items=[EntityListItem(**r) for r in rows], total=total, limit=limit, offset=offset
    )


@router.get("/entities/{norm_name}", response_model=EntityDetail)
def get_entity(norm_name: str) -> EntityDetail:
    entity = graph_store.get_entity(norm_name)
    if entity is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": "Không tìm thấy thực thể."},
        )
    return EntityDetail(**entity)
