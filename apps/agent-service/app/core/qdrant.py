"""Client Qdrant dùng chung + bootstrap collection cho chunk vector.

Qdrant point id BẮT BUỘC là uint hoặc UUID — `chunk_id` của dự án là chuỗi
("lichsu_clean-000001") nên không dùng trực tiếp được. `point_id_for()` map
deterministic chunk_id -> UUID5 (cùng chunk_id luôn ra cùng id => re-upsert ghi đè,
idempotent, ổn định xuyên máy). `chunk_id` thật được giữ trong payload để join về
Postgres `rag_chunks.chunk_id`.
"""

from __future__ import annotations

import uuid
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

from app.core.config import get_settings
from app.core.embedding import EMBEDDING_DIM

__all__ = ["get_qdrant_client", "ensure_chunks_collection", "point_id_for"]

# Namespace cố định cho UUID5 từ chunk_id. KHÔNG đổi giá trị này sau khi đã index,
# nếu không point id sẽ lệch và tạo bản trùng thay vì ghi đè.
_NS = uuid.UUID("a3f1c2e4-5b6d-4e8a-9c0f-1d2e3f4a5b6c")


@lru_cache(maxsize=1)
def get_qdrant_client() -> QdrantClient:
    s = get_settings()
    if not s.qdrant_host:
        raise RuntimeError("Thiếu QDRANT_HOST trong .env.")
    return QdrantClient(
        host=s.qdrant_host,
        port=s.qdrant_port,
        api_key=s.qdrant_api_key or None,
        # Qdrant remote chạy HTTP thuần trên :6333. Có api_key => client mặc định
        # https=True và vỡ SSL trên cổng http; ép http (giống cách LightRAG dùng
        # QDRANT_URL=http://...).
        https=False,
        timeout=60,
    )


def point_id_for(chunk_id: str) -> str:
    """Map chunk_id (chuỗi) -> UUID5 deterministic làm Qdrant point id."""
    return str(uuid.uuid5(_NS, chunk_id))


def ensure_chunks_collection(client: QdrantClient | None = None) -> str:
    """Tạo collection chunk vector nếu chưa có (cosine, dim = embedding model)."""
    client = client or get_qdrant_client()
    name = get_settings().qdrant_collection
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
        )
    return name
