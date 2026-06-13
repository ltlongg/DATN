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
from qdrant_client.models import PointStruct

from app.core.config import get_settings
from app.core.embedding import embed_texts
from app.core.qdrant import get_qdrant_client, point_id_for
from app.tools.graph_rag.chunks import CHUNK_VECTOR_META_FIELDS

__all__ = ["upsert_chunk_vectors"]

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
    collection = get_settings().qdrant_collection

    total = 0
    log.info("Embed model lần đầu có thể tốn vài chục giây (cold start)...")
    for start in range(0, len(records), batch_size):
        batch = records[start : start + batch_size]
        texts = [str(r.get("embedding_text") or r["text"]) for r in batch]
        vectors = asyncio.run(embed_texts(texts))  # (n, EMBEDDING_DIM), L2-normalized
        points = [
            PointStruct(
                id=point_id_for(r["chunk_id"]),
                vector=vec.tolist(),
                payload=_payload(r),
            )
            for r, vec in zip(batch, vectors)
        ]
        client.upsert(collection_name=collection, points=points, wait=True)
        total += len(points)
        log.info("Upsert Qdrant: %d/%d", total, len(records))
    return total
