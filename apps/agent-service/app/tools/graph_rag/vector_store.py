"""Index chunk vector vào Qdrant.

Embed `embedding_text` (đã kèm context heading) bằng model tiếng Việt, upsert vào
collection `history_vn_chunks`. Point id = uuid5(chunk_id) (deterministic => re-upsert
ghi đè, idempotent). Payload = đúng `CHUNK_VECTOR_META_FIELDS` (không lưu text — Postgres
là source of truth), `chunk_id` thật nằm trong payload để join ngược.

CLI sync gọi `embed_texts` (async) qua `asyncio.run` — phải ở main thread, KHÔNG gọi
trong thread của ThreadPoolExecutor.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Fusion,
    FusionQuery,
    PointStruct,
    Prefetch,
    SparseVector,
)

from app.core.config import get_settings
from app.core.embedding import embed_texts
from app.core.qdrant import get_qdrant_client, point_id_for
from app.core.sparse import encode_documents, encode_query
from app.schemas.retrieval import RetrievalBackendError, RetrievalCandidate
from app.tools.graph_rag.chunks import CHUNK_VECTOR_META_FIELDS

__all__ = ["upsert_chunk_vectors", "search_vector", "search_dense_sparse", "search_bm25"]

log = logging.getLogger(__name__)

def _payload(record: dict[str, Any]) -> dict[str, Any]:
    return {field: record.get(field) for field in CHUNK_VECTOR_META_FIELDS}

def upsert_chunk_vectors(
    records: list[dict[str, Any]],
    *,
    batch_size: int = 128,
    client: QdrantClient | None = None,
) -> int:
    """Embed + upsert chunk vector theo batch. Trả số point đã ghi."""
    if not records:
        return 0

    client = client or get_qdrant_client()
    settings = get_settings()
    collection = settings.qdrant_collection
    sparse_name = settings.sparse_vector_name

    total = 0
    log.info("Embed model lần đầu có thể tốn vài chục giây (cold start)...")
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        texts = [str(r.get("embedding_text") or r["text"]) for r in batch]
        vectors = asyncio.run(embed_texts(texts))  # (n, EMBEDDING_DIM), L2-normalized
        sparse = encode_documents(texts)  # [(indices, values), ...] cùng thứ tự texts
        points = [
            PointStruct(
                id=point_id_for(r["chunk_id"]),
                # dense unnamed (key "") + named sparse "bm25" trên cùng point.
                vector={
                    "": vec.tolist(),
                    sparse_name: SparseVector(indices=si, values=sv),
                },
                payload=_payload(r),
            )
            for r, vec, (si, sv) in zip(batch, vectors, sparse)
        ]
        client.upsert(collection_name=collection, points=points, wait=True)
        total += len(points)
        log.info("Upsert Qdrant: %d/%d", total, len(records))
    return total

async def search_vector(
    query: str,
    *,
    top_k: int | None = None,
    client: QdrantClient | None = None,
) -> list[RetrievalCandidate]:
    """Embed query trần -> Qdrant search -> RetrievalCandidate[] (chưa hydrate text).

    Query embed trần (chỉ câu hỏi), KHÁC document embed (có prepend heading) — dense
    retrieval thường chịu được asymmetry này (xem plan §Traditional). Point thiếu
    `chunk_id` trong payload -> bỏ + log (không join ngược Postgres được).
    """
    settings = get_settings()
    k = top_k if top_k is not None else settings.rag_top_k

    try:
        vectors = await embed_texts([query])
    except Exception as exc:  # model lỗi/không nạp được
        raise RetrievalBackendError("embedding_failed") from exc
    if len(vectors) == 0:
        return []

    try:
        client = client or get_qdrant_client()
        response = await asyncio.to_thread(
            client.query_points,
            collection_name=settings.qdrant_collection,
            query=vectors[0].tolist(),
            limit=k,
            with_payload=True,
        )
    except Exception as exc:  # thiếu env/client hoặc kết nối lỗi
        raise RetrievalBackendError("qdrant_unavailable") from exc

    return _points_to_candidates(response.points, "vector")

def _points_to_candidates(points: list, source: str) -> list[RetrievalCandidate]:
    """Map Qdrant points -> RetrievalCandidate, rank liền mạch, bỏ point thiếu chunk_id."""
    candidates: list[RetrievalCandidate] = []
    for point in points:
        chunk_id = (point.payload or {}).get("chunk_id")
        if not chunk_id:
            log.warning("Qdrant point %s thiếu chunk_id trong payload, bỏ qua.", point.id)
            continue
        candidates.append(
            RetrievalCandidate(
                chunk_id=str(chunk_id),
                source=source,  # type: ignore[arg-type]
                rank=len(candidates) + 1,
                score=point.score,
            )
        )
    return candidates

async def search_dense_sparse(
    query: str,
    *,
    top_k: int | None = None,
    bm25_top_k: int | None = None,
    client: QdrantClient | None = None,
) -> list[RetrievalCandidate]:
    """Dense + sparse BM25 fuse RRF SERVER-SIDE (Qdrant Query API) -> candidate đã gộp.

    Dùng cho traditional mode: 1 call, Qdrant tự RRF dense (default) + sparse (`bm25`).
    `source="vector"` vì sau fusion không tách được đóng góp dense/sparse. Hybrid mode KHÔNG
    dùng hàm này (nó fuse client-side để gộp thêm graph — xem `tools/hybrid`).

    `top_k`/`bm25_top_k` None -> fallback settings (Cấu hình hệ thống truyền giá trị admin).
    `top_k` áp cho CẢ dense prefetch lẫn limit fusion cuối (giữ 2 giá trị bằng nhau như trước).
    """
    settings = get_settings()
    k = top_k if top_k is not None else settings.rag_top_k
    bm25_k = bm25_top_k if bm25_top_k is not None else settings.bm25_top_k

    try:
        vectors = await embed_texts([query])
    except Exception as exc:  # model lỗi/không nạp được
        raise RetrievalBackendError("embedding_failed") from exc
    if len(vectors) == 0:
        return []
    sparse_indices, sparse_values = await asyncio.to_thread(encode_query, query)

    try:
        client = client or get_qdrant_client()
        response = await asyncio.to_thread(
            client.query_points,
            collection_name=settings.qdrant_collection,
            prefetch=[
                Prefetch(query=vectors[0].tolist(), limit=k),
                Prefetch(
                    query=SparseVector(indices=sparse_indices, values=sparse_values),
                    using=settings.sparse_vector_name,
                    limit=bm25_k,
                ),
            ],
            query=FusionQuery(fusion=Fusion.RRF),
            limit=k,
            with_payload=True,
        )
    except Exception as exc:  # thiếu env/client hoặc kết nối lỗi
        raise RetrievalBackendError("qdrant_unavailable") from exc

    return _points_to_candidates(response.points, "vector")

async def search_bm25(
    query: str,
    *,
    top_k: int | None = None,
    client: QdrantClient | None = None,
) -> list[RetrievalCandidate]:
    """Sparse BM25-only -> candidate `source="sparse"`. Primitive cho hybrid (fuse client-side).

    KHÔNG fusion ở đây (hybrid tự RRF gộp với dense + graph). KHÔNG cần embed dense -> rẻ
    hơn search_dense_sparse.
    """
    settings = get_settings()
    k = top_k if top_k is not None else settings.bm25_top_k
    sparse_indices, sparse_values = await asyncio.to_thread(encode_query, query)

    try:
        client = client or get_qdrant_client()
        response = await asyncio.to_thread(
            client.query_points,
            collection_name=settings.qdrant_collection,
            query=SparseVector(indices=sparse_indices, values=sparse_values),
            using=settings.sparse_vector_name,
            limit=k,
            with_payload=True,
        )
    except Exception as exc:  # thiếu env/client hoặc kết nối lỗi
        raise RetrievalBackendError("qdrant_unavailable") from exc

    return _points_to_candidates(response.points, "sparse")
