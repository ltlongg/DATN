"""Contract tầng retrieval query-side (traditional / hybrid).

Hai trục dữ liệu TÁCH BIỆT, đừng trộn:
- `chunks` (RetrievedChunk) — đường provenance: text chunk đã hydrate từ Postgres.
- `graph_context` (GraphContextItem) — NỘI DUNG đã chưng cất từ KG (description của
  entity/relation), đưa THẲNG cho LLM, KHÔNG qua RRF. Chỉ hybrid điền.

Không dùng một field `score` chung: cosine (vector), rank-based (graph), RRF, reranker
là bốn thang đo khác bản chất nên mỗi cái một field riêng để debug/ablation.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RetrievalMode = Literal["traditional", "hybrid"]
# "vector" = dense; "sparse" = BM25 keyword; "graph" = GraphRAG. Hybrid fuse cả ba qua RRF.
# "graph" ở đây là NGUỒN candidate bên trong hybrid, KHÔNG phải một `RetrievalMode`.
CandidateSource = Literal["vector", "graph", "sparse"]

class RetrievalBackendError(RuntimeError):
    """Lỗi backend retrieval (Qdrant/Neo4j/embedding). `code` để phân loại + test.

    Dùng cho các nhánh không thể tiếp tục (vd thiếu client, embedding fail, cả hai
    backend chết). KHÔNG dùng cho "không match seed" / "empty result" — những case đó
    trả result rỗng, không raise (xem plan §Error handling).
    """

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code

class RetrievalCandidate(BaseModel):
    """Candidate nhẹ mỗi retriever trả ra (chưa hydrate text). Hybrid hydrate 1 lần."""

    chunk_id: str
    source: CandidateSource
    rank: int
    score: float | None = None
    debug: dict[str, object] = Field(default_factory=dict)

class RetrievedChunk(BaseModel):
    """Chunk đã hydrate full text + metadata từ Postgres `rag_chunks`."""

    chunk_id: str
    text: str
    metadata: dict[str, object]
    heading_path: list[str]
    vector_score: float | None = None
    graph_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None
    sources: list[CandidateSource] = Field(default_factory=list)
    debug: dict[str, object] = Field(default_factory=dict)

class GraphContextItem(BaseModel):
    """Tri thức đã chưng cất từ KG, đưa THẲNG cho LLM (không chỉ trỏ tới chunk).

    `kind="entity"`: dùng `name`/`norm_name` (các field `source_*`/`target_*`/`keyword`
    để None). `kind="relation"`: cạnh (source)-[keyword]->(target) — lưu CÓ CẤU TRÚC,
    KHÔNG nhồi vào một string (string render prompt thì derive lúc build prompt).
    Provenance giữ qua `source_chunk_ids`; `matched_seed` ghi seed nào dẫn tới item.
    """

    kind: Literal["entity", "relation"]
    name: str | None = None
    norm_name: str | None = None
    source_name: str | None = None
    source_norm: str | None = None
    target_name: str | None = None
    target_norm: str | None = None
    keyword: str | None = None
    description: str  # gộp từ Neo4j descriptions[] (đã dedup)
    source_chunk_ids: list[str] = Field(default_factory=list)
    matched_seed: str | None = None

    def dedup_key(self) -> tuple[str, ...]:
        """Khóa cấu trúc để dedup item xuyên seed (entity vs relation)."""
        if self.kind == "entity":
            return ("entity", self.norm_name or "")
        return (
            "relation",
            self.source_norm or "",
            self.keyword or "",
            self.target_norm or "",
        )

class RetrievalResult(BaseModel):
    mode: RetrievalMode
    query: str
    chunks: list[RetrievedChunk]
    graph_context: list[GraphContextItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    debug: dict[str, object] = Field(default_factory=dict)
