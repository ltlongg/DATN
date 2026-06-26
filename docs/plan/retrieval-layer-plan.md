# Retrieval Layer Plan

## Mục tiêu

Xây lại tầng retrieval query-side cho `agent-service` sau khi đã revert code cũ.
Tầng này chỉ chịu trách nhiệm lấy context có provenance từ corpus lịch sử Việt Nam:

- Traditional RAG: semantic/vector search qua Qdrant.
- GraphRAG query-side: tìm entity/relationship trong Neo4j, rồi truy ngược `source_chunk_ids`.
- Hybrid retrieval: phối hợp traditional + graph, dedupe/fuse/rerank, trả chunk đã hydrate từ Postgres.

Nguyên tắc chốt: **tách implementation traditional và graph riêng, nhưng default runtime dùng hybrid**.
Hybrid là lớp composition, không phải một cục monolith nuốt hết logic retrieval.

## Trạng thái hiện tại sau revert

Repo hiện đã có indexing/storage primitives, nhưng chưa có retrieval query-side hoàn chỉnh:

- Postgres source of truth cho chunks: `app/tools/graph_rag/chunk_store.py`
  - `rag_chunks.chunk_id` là primary key.
  - `get_rag_chunks_by_ids()` hydrate full text + metadata theo danh sách `chunk_id`.
- Qdrant client + vector indexing: `app/core/qdrant.py`, `app/tools/graph_rag/vector_store.py`
  - Hiện mới có upsert vector, chưa có vector search.
  - Qdrant payload có `chunk_id`, không lưu text.
- Neo4j client + graph merge: `app/core/neo4j.py`, `app/tools/graph_rag/graph_store.py`
  - Hiện mới có `merge_graph()`, chưa có query-side `search_graph()`.
  - Node `:Entity` dùng `norm_name` unique, edge `:REL` tích lũy `source_chunk_ids`.
- Alias resolver đã có: `app/indexing/graph/alias.py::resolve()`.
  - Query-side GraphRAG bắt buộc dùng cùng resolver này để đối xứng với indexing.
- `api/`, `orchestrator/`, `tools/traditional_rag/`, `tools/hybrid/` chưa build.

## Quyết định kiến trúc

### 1. Tách traditional, graph, hybrid

```text
User question
  │
  ├─ traditional_rag.retrieve()
  │    └─ embed query -> Qdrant search -> chunk candidates
  │
  ├─ graph_rag.retrieve()
  │    └─ resolve aliases -> Neo4j seed/expand -> chunk candidates
  │
  └─ hybrid.retrieve()
       └─ run both -> RRF/dedupe -> hydrate once -> rerank -> final chunks
```

Lý do:

- Traditional và Graph có failure mode khác nhau.
- Tách riêng giúp unit test, debug và làm ablation cho đồ án.
- Hybrid vẫn là đường chính cho answer/orchestrator vì bù điểm yếu của từng mode.

### 2. Mỗi retriever trả candidate nhẹ trước, hydrate một lần

Không để vector retriever fetch full text, graph retriever fetch full text, rồi hybrid fetch lại.
Mỗi retriever trả `RetrievalCandidate` nhẹ:

```python
RetrievalCandidate(
    chunk_id="lichsu_clean-000123",
    source="vector",  # "vector" | "graph"
    rank=1,
    score=0.82,
    debug={"matched_entity": "..."},
)
```

Hybrid gom `chunk_id`, fuse/dedupe, rồi hydrate từ Postgres một lần bằng
`get_rag_chunks_by_ids()`.

### 3. Graph-only không làm default

GraphRAG hữu ích cho entity/relationship, nhưng dễ nhiễu bởi hub entity như
`Pháp`, `Việt Nam`, `quân Pháp`. Vì vậy:

- Orchestrator/API default dùng `hybrid`.
- `traditional` và `graph` là mode debug/eval/fallback.
- Router sau này có thể chọn mode, nhưng câu quan hệ/cause cũng nên đi `hybrid` trước,
  không graph-only ngay.

### 4. Async boundary rõ ràng

FastAPI/LangGraph sau này chạy async, nhưng các client hiện tại phần lớn sync.
Plan này không bắt buộc chuyển hết sang async driver ngay, nhưng mọi sync I/O trong
coroutine phải được bọc bằng `asyncio.to_thread()`.

## NOT in scope

- Không build LangGraph orchestrator.
- Không build `/ask` API.
- Không synthesize answer bằng LLM.
- Không build citation validation LLM output.
- Không build visualization/map/timeline.
- Không re-index dataset.
- Không chạy lại graph/timeline/geocoding extraction.
- Không expose mode selection ra frontend.

## Module/file dự kiến

```text
apps/agent-service/app/
  core/
    config.py                 # thêm retrieval/rerank knobs
    reranker.py               # optional cross-encoder reranker

  schemas/
    retrieval.py              # Pydantic retrieval contracts

  tools/
    graph_rag/
      vector_store.py         # thêm search_vector()
      graph_store.py          # thêm search/match graph query helpers
      retriever.py            # graph retrieval facade

    traditional_rag/
      __init__.py
      retriever.py            # vector retrieval facade

    hybrid/
      __init__.py
      retriever.py            # fanout + fusion + rerank
```

Giữ diff vừa phải: ưu tiên thêm function vào store hiện có thay vì tạo nhiều service/class mới.

## Schema contract

Thêm `app/schemas/retrieval.py`.

```python
from typing import Literal
from pydantic import BaseModel, Field

RetrievalMode = Literal["traditional", "graph", "hybrid"]
CandidateSource = Literal["vector", "graph"]


class RetrievalCandidate(BaseModel):
    chunk_id: str
    source: CandidateSource
    rank: int
    score: float | None = None
    debug: dict[str, object] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
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


class RetrievalResult(BaseModel):
    mode: RetrievalMode
    query: str
    chunks: list[RetrievedChunk]
    warnings: list[str] = Field(default_factory=list)
    debug: dict[str, object] = Field(default_factory=dict)
```

Lưu ý: không dùng một field `score` chung cho mọi thứ. Cosine score, graph rank,
RRF và reranker score không cùng thang đo.

## Traditional RAG

### Luồng

```text
question
  -> embed_texts([question])
  -> Qdrant search top rag_top_k
  -> lấy payload.chunk_id + vector score
  -> return RetrievalCandidate[]
```

### Implementation notes

`vector_store.py` thêm:

```python
async def search_vector(
    query: str,
    *,
    top_k: int | None = None,
    client: QdrantClient | None = None,
) -> list[RetrievalCandidate]:
    ...
```

Chi tiết:

- Dùng `app.core.embedding.embed_texts()` để sinh vector query.
- Dùng collection `settings.qdrant_collection`.
- Qdrant payload phải có `chunk_id`; nếu thiếu thì bỏ candidate và warning/debug.
- Không hydrate text ở đây.
- Không filter cứng bằng `actors/events/locations` trong bản đầu.
- Có thể thêm filter nhẹ theo `times` hoặc `heading_path` sau khi có eval, nhưng không làm trước.

## GraphRAG query-side

### Luồng

```text
question
  -> generate/normalize seed entity candidates
  -> resolve(alias) bằng app.indexing.graph.alias.resolve()
  -> MATCH (:Entity {norm_name})
  -> expand 1-hop qua :REL
  -> collect node/edge source_chunk_ids
  -> rank chunk ids
  -> return RetrievalCandidate[]
```

### Seed entity matching

MVP nên deterministic, chưa dùng LLM router/extractor online để tránh thêm latency/cost.

Plan:

1. Tạo cụm n-gram từ question, ưu tiên 2-8 từ.
2. Với mỗi cụm:
   - strip punctuation nhẹ,
   - gọi `resolve(phrase)` để lấy `(canonical_name, canonical_norm)`,
   - exact match Neo4j theo `norm_name`.
3. Fallback substring search cho entity dài xuất hiện trong question.
4. Sort seed:
   - exact/alias match trước,
   - cụm dài hơn trước,
   - entity ít hub hơn trước.

### Hub guard

Graph có các entity cực rộng như `Pháp`, `Việt Nam`, `quân Pháp`. Plan cần guard ngay từ đầu:

- Bỏ seed entity quá ngắn/generic, ví dụ 1 từ phổ biến nếu không có context mạnh.
- Cap số `source_chunk_ids` lấy từ một seed.
- Hạ điểm seed có degree/source count quá lớn.
- Limit seed count: `graph_max_seed_entities`.
- Limit chunk per seed: `graph_max_chunks_per_seed`.

### Neo4j query helpers

`graph_store.py` thêm các helper sync, rồi retriever async bọc `to_thread()` nếu cần:

```python
def match_seed_entities(question: str, *, limit: int) -> list[GraphSeed]:
    ...

def search_graph(question: str, *, top_k: int) -> list[RetrievalCandidate]:
    ...
```

Có thể dùng Cypher 1-hop:

```cypher
MATCH (seed:Entity {norm_name: $norm_name})
OPTIONAL MATCH (seed)-[r:REL]-(neighbor:Entity)
RETURN seed, collect(r), collect(neighbor)
```

Ranking chunk gợi ý:

- + seed exact/alias hit
- + edge source chunk hit
- + multiple seeds cùng trỏ tới chunk
- - hub penalty
- stable tie-break bằng `chunk_id`

## Hybrid retrieval

### Luồng

```text
question
  ├─ traditional candidates
  └─ graph candidates
        ↓
  dedupe by chunk_id
        ↓
  Reciprocal Rank Fusion
        ↓
  hydrate top hybrid_candidate_k from Postgres
        ↓
  rerank top candidates
        ↓
  return top rerank_top_k chunks
```

### RRF

```python
rrf_score = sum(1 / (hybrid_rrf_k + rank_from_source))
```

Default `hybrid_rrf_k = 60` là hợp lý cho RRF. Không cố normalize cosine score với graph
score trong bản đầu vì hai thang đo khác bản chất.

### Reranker

Thêm `app/core/reranker.py` optional:

- Nếu `reranker_model` rỗng: skip rerank, trả theo RRF.
- Nếu có model: dùng `sentence-transformers` CrossEncoder trong `asyncio.to_thread()`.
- Input pair: `(question, chunk.text)`.
- Output: `rerank_score`, sort desc.

Default model có thể để configurable, ví dụ `BAAI/bge-reranker-v2-m3`, nhưng không hardcode
phụ thuộc vào một model nếu môi trường chưa tải/cache.

## Config knobs

Thêm vào `Settings`:

```python
rag_top_k: int = 20
graph_top_k: int = 20
hybrid_candidate_k: int = 30
rerank_top_k: int = 8
hybrid_rrf_k: int = 60
reranker_model: str = ""
graph_max_seed_entities: int = 5
graph_max_chunks_per_seed: int = 20
graph_hub_source_count_threshold: int = 80
```

Không thêm quá nhiều knob lúc đầu. Các giá trị này đủ để tune retrieval mà không làm config nở.

## Error handling

### Traditional

- Thiếu Qdrant env/client lỗi: raise `RetrievalBackendError("qdrant_unavailable")`.
- Query embedding lỗi: raise `RetrievalBackendError("embedding_failed")`.
- Qdrant trả point thiếu `chunk_id`: skip + warning.

### Graph

- Thiếu Neo4j env/client lỗi: raise `RetrievalBackendError("neo4j_unavailable")`.
- Không match seed: trả empty result, không raise.
- Seed toàn hub/generic: trả empty + warning/debug.

### Hybrid

- Một backend fail, backend còn lại có kết quả: trả partial result + warning.
- Cả hai backend fail: raise `RetrievalBackendError("all_backends_failed")`.
- Hydrate thiếu một số `chunk_id`: bỏ chunk thiếu + warning.
- Empty final chunks: trả `RetrievalResult(chunks=[])`, để orchestrator quyết định honest answer.

## Test plan

### Test diagram

```text
traditional
  question -> embed -> qdrant hits -> candidates
      ├─ qdrant ok
      ├─ qdrant missing chunk_id
      └─ qdrant unavailable

graph
  question -> alias resolve -> seed match -> 1-hop expand -> candidates
      ├─ exact entity
      ├─ alias entity
      ├─ no seed
      ├─ hub seed
      └─ neo4j unavailable

hybrid
  vector candidates + graph candidates -> RRF -> hydrate -> rerank
      ├─ overlapping chunk_ids
      ├─ vector only
      ├─ graph only
      ├─ one backend fail
      ├─ both backends fail
      └─ hydrate missing chunks
```

### Unit tests nên có

- `test_search_vector_returns_candidates_from_qdrant_payload`
- `test_search_vector_skips_point_missing_chunk_id`
- `test_graph_retrieval_resolves_alias_before_matching_norm_name`
- `test_graph_retrieval_ignores_or_penalizes_hub_seed`
- `test_graph_retrieval_empty_when_no_seed`
- `test_hybrid_rrf_dedupes_same_chunk_from_vector_and_graph`
- `test_hybrid_partial_when_qdrant_fails_but_graph_succeeds`
- `test_hybrid_raises_when_all_backends_fail`
- `test_hybrid_hydrates_chunks_once_in_fused_order`
- `test_reranker_can_be_disabled`
- `test_reranker_reorders_chunks_when_enabled_with_mock`

### Integration tests optional

Đánh dấu skip nếu thiếu env hoặc backend remote:

- hỏi “Trương Định” phải có chunk liên quan.
- hỏi alias “Nguyễn Ái Quốc” phải match node/chunk canonical “Hồ Chí Minh” nếu graph đã index alias.
- hỏi quan hệ “Phan Bội Châu liên quan gì đến Cường Để?” hybrid phải có cả graph signal và text chunk.

## Implementation order

1. Tạo `schemas/retrieval.py`.
2. Thêm config knobs.
3. Thêm `search_vector()` + tests mock Qdrant.
4. Thêm graph query helpers + tests mock Neo4j/session.
5. Thêm `traditional_rag/retriever.py`.
6. Thêm `graph_rag/retriever.py`.
7. Thêm `hybrid/retriever.py` với RRF + hydrate once.
8. Thêm optional reranker.
9. Chạy ruff/mypy/pytest.

## Acceptance criteria

- Có thể gọi:
  - `retrieve_traditional(question)`
  - `retrieve_graph(question)`
  - `retrieve_hybrid(question)`
- Hybrid là path mặc định cho orchestrator sau này.
- Mọi result có `chunk_id`, `text`, `metadata`, `heading_path`.
- Không có N+1 hydrate Postgres trong hybrid.
- Alias query-side dùng cùng `resolve()` với indexing.
- Empty retrieval không hallucinate; chỉ trả empty result cho tầng orchestrator xử lý.
- Unit tests cover core branching/error paths.

