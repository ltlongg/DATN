"""Admin documents router (mock metadata) — CHỈ role admin (require_admin trên mọi route).

MVP chưa upload/index file thật; chỉ quản lý metadata. Upload + indexing thật là "Sau MVP".
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.core.errors import AppError
from app.models import document as doc_repo
from app.models.document import Document
from app.schemas.common import OkResponse
from app.schemas.document import DocumentCreate, DocumentOut, DocumentUpdate

# require_admin áp cho toàn router -> teacher gọi bất kỳ route nào đều nhận 403.
router = APIRouter(dependencies=[Depends(require_admin)])


def _to_out(doc: Document) -> DocumentOut:
    return DocumentOut(**doc.model_dump())


@router.get("", response_model=list[DocumentOut])
async def list_documents() -> list[DocumentOut]:
    docs = await anyio.to_thread.run_sync(doc_repo.list_documents)
    return [_to_out(d) for d in docs]


@router.post("", response_model=DocumentOut, status_code=201)
async def create_document(body: DocumentCreate) -> DocumentOut:
    doc = await anyio.to_thread.run_sync(
        lambda: doc_repo.create_document(body.name, body.type, body.status, body.chunk_count)
    )
    return _to_out(doc)


@router.patch("/{document_id}", response_model=DocumentOut)
async def update_document(document_id: str, body: DocumentUpdate) -> DocumentOut:
    fields = body.model_dump(exclude_unset=True)
    doc = await anyio.to_thread.run_sync(doc_repo.update_document, document_id, fields)
    if doc is None:
        raise AppError(404, "not_found", "Không tìm thấy tài liệu.")
    return _to_out(doc)


@router.delete("/{document_id}", response_model=OkResponse)
async def delete_document(document_id: str) -> OkResponse:
    deleted = await anyio.to_thread.run_sync(doc_repo.delete_document, document_id)
    if not deleted:
        raise AppError(404, "not_found", "Không tìm thấy tài liệu.")
    return OkResponse()
