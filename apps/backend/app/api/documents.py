"""Admin documents router — CHỈ role admin (require_admin trên mọi route).

Danh mục tài liệu nguồn, NỐI xuống kho tri thức thật qua `source_file`: số chunk/sự kiện
là đếm thật từ `rag_chunks`/`timeline_events` (xem models/document.py). MVP chưa upload +
index file thật từ UI; xoá document chỉ xoá khỏi danh mục, KHÔNG đụng kho.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, Depends

from app.api.deps import require_admin
from app.core.errors import AppError
from app.models import document as doc_repo
from app.models.document import Document
from app.schemas.common import OkResponse
from app.schemas.document import DocumentCreate, DocumentOut, DocumentUpdate, KbSourceOut

# require_admin áp cho toàn router -> user thường gọi bất kỳ route nào đều nhận 403.
router = APIRouter(dependencies=[Depends(require_admin)])

def _to_out(doc: Document) -> DocumentOut:
    return DocumentOut(**doc.model_dump())

@router.get("", response_model=list[DocumentOut])
async def list_documents() -> list[DocumentOut]:
    docs = await anyio.to_thread.run_sync(doc_repo.list_documents)
    return [_to_out(d) for d in docs]

@router.get("/sources", response_model=list[KbSourceOut])
async def list_kb_sources() -> list[KbSourceOut]:
    """Nguồn CÓ THẬT trong kho tri thức (dropdown lọc chunk ở KB Inspector)."""
    sources = await anyio.to_thread.run_sync(doc_repo.list_kb_sources)
    return [KbSourceOut(**s.model_dump()) for s in sources]

@router.post("", response_model=DocumentOut, status_code=201)
async def create_document(body: DocumentCreate) -> DocumentOut:
    """Tạo tài liệu chưa gắn nguồn. Tài liệu đã có chunk trong kho KHÔNG tạo qua đây — nó
    tự hiện ở danh mục (xem models/document.py::sync_kb_documents)."""
    doc = await anyio.to_thread.run_sync(
        lambda: doc_repo.create_document(body.name, body.type, body.status)
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
    doc = await anyio.to_thread.run_sync(doc_repo.get_document, document_id)
    if doc is None:
        raise AppError(404, "not_found", "Không tìm thấy tài liệu.")
    if doc.source_file:
        # Xoá khỏi danh mục vô nghĩa khi chunk vẫn nằm trong kho: lần list sau
        # sync_kb_documents dựng lại ngay. Xoá thật = xoá cả chunk khỏi kho (Bước 1).
        raise AppError(
            409,
            "document_indexed",
            f"“{doc.name}” còn {doc.chunk_count} chunk trong kho tri thức nên không xoá khỏi "
            f"danh mục được. Cần gỡ tài liệu khỏi kho trước (chưa hỗ trợ).",
        )
    await anyio.to_thread.run_sync(doc_repo.delete_document, document_id)
    return OkResponse()
