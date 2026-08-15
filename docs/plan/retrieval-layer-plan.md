# Retrieval Layer Plan

> **Cập nhật 2026-06-26**: chốt thêm 2 thay đổi thiết kế (đổi contract — làm TRƯỚC khi code
> hybrid): (1) **graph đóng góp NỘI DUNG, không chỉ trỏ chunk** — đính `descriptions` của
> entity/relation đã trích offline vào `RetrievalResult.graph_context` cho LLM (xem §Schema
> + §GraphRAG query-side); (2) **seed entity matching tách 2 bước** — A: sinh mention (LLM
> gộp vào call rewrite query của orchestrator = zero latency thêm; fallback token-match
> deterministic làm baseline/standalone), B: grounding mention→`norm_name` bằng
> inverted-index + `resolve()` (luôn dùng); bỏ hẳn n-gram brute-force + Cypher exact-match
> (xem §Seed entity matching). Kèm ghi chú: RRF chỉ dùng rank, ranh giới query-rewriting,
> handoff visualization, bộ eval ablation. Hai điểm (1)+(2) cùng alias resolution là
> contribution chính của đồ án (graph-as-content, không chỉ là index phụ).
>
> **Hiệu chỉnh sau review 2026-06-26** (5 điểm, đọc kỹ trước khi code): (a) grounding ground
> bằng `resolve()` trên mention GỐC có dấu (alias_map key CÓ dấu — `normalize_name` giữ dấu);
> **MVP bỏ hẳn index không dấu** (LLM trích mention đã đúng chính tả; thêm sau nếu eval cần);
> (b) `seed_mentions` là kwarg xuyên suốt
> `match_seed_entities`/`search_graph`/`retrieve_graph`; (c) `GraphContextItem` lưu relation
> CÓ CẤU TRÚC (`source_*`/`target_*`/`keyword`), không nhồi vào 1 string; (d) citation:
> hybrid hydrate kèm `source_chunk_ids` của `graph_context` để validator không drop nguồn
> (rule B mặc định); (e) `entity_index.json` phải rebuild khi `alias_map`/KG version đổi.

## Mục tiêu

Xây lại tầng retrieval query-side cho `agent-service` sau khi đã revert code cũ.
Tầng này chỉ chịu trách nhiệm lấy context có provenance từ corpus lịch sử Việt Nam:

- Traditional RAG: semantic/vector search qua Qdrant.
- GraphRAG query-side: tìm entity/relationship trong Neo4j, truy ngược `source_chunk_ids`
  **và** thu `descriptions` đã chưng cất để đưa thẳng cho LLM (không chỉ làm bộ định tuyến
  tới chunk).
- Hybrid retrieval: phối hợp traditional + graph, dedupe/fuse/rerank, trả chunk đã hydrate
  từ Postgres **kèm `graph_context`**.

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

### 5. Input là standalone query (contextualize thuộc orchestrator)

`retrieve_*(question)` **giả định nhận một standalone query** đã đủ ngữ cảnh. Câu trỏ
lượt trước ("nó diễn ra năm nào?", "ông ấy làm gì tiếp?") sẽ retrieve ra rỗng nếu chưa
rewrite. Việc gộp `history` + câu hỏi thành standalone query là **trách nhiệm của
orchestrator** (xem `orchestrator-plan.md` — "build query from question/history"), KHÔNG
phải của tầng retrieval. Retrieval không đụng tới `history`.

### 6. Graph là NGUỒN NỘI DUNG, không chỉ là index phụ

Indexing đã trích `descriptions` cho mỗi entity/relation và tích lũy xuyên chunk vào
Neo4j (`graph_store.py`). Query-side **phải khai thác** phần này: ngoài việc truy
`source_chunk_ids` để gom chunk (đường provenance), graph retriever thu luôn description
của các entity/relation đã match và trả về `RetrievalResult.graph_context`. Orchestrator
đưa block này cho LLM **song song** với chunk text. Lý do: câu quan hệ/nhân-quả
("Phan Bội Châu liên quan gì đến Cường Để?") được trả lời sắc hơn khi LLM nhận thẳng cạnh
đã chưng cất thay vì phải tự suy lại từ text thô. Provenance vẫn giữ qua `source_chunk_ids`
đính kèm mỗi item.

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

class GraphContextItem(BaseModel):
    """Tri thức đã chưng cất từ KG, đưa THẲNG cho LLM (không chỉ trỏ tới chunk).

    `kind="entity"`: dùng `name`/`norm_name` (các field `*_target`, `keyword` để None).
    `kind="relation"`: cạnh (source)-[keyword]->(target) — dùng field cấu trúc, KHÔNG nhồi
    vào một string. String "source -[keyword]-> target" để render prompt thì derive lúc build
    prompt, nhưng LƯU có cấu trúc để eval/dedupe/debug khớp chính xác.
    Provenance giữ qua `source_chunk_ids`; `matched_seed` ghi seed nào trong query dẫn tới.
    """

    kind: Literal["entity", "relation"]
    # entity: name = display, norm_name = khóa. relation: dùng source_*/target_*/keyword.
    name: str | None = None
    norm_name: str | None = None
    source_name: str | None = None
    source_norm: str | None = None
    target_name: str | None = None
    target_norm: str | None = None
    keyword: str | None = None
    description: str                # gộp từ Neo4j (descriptions[] đã dedup)
    source_chunk_ids: list[str] = Field(default_factory=list)
    matched_seed: str | None = None

class RetrievalResult(BaseModel):
    mode: RetrievalMode
    query: str
    chunks: list[RetrievedChunk]
    graph_context: list[GraphContextItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    debug: dict[str, object] = Field(default_factory=dict)
```

Lưu ý: không dùng một field `score` chung cho mọi thứ. Cosine score, graph rank,
RRF và reranker score không cùng thang đo.

`graph_context` **chỉ graph retriever (và hybrid) điền**; traditional để rỗng. Đây là
phần "content" của GraphRAG — KHÁC với `chunks` (đường provenance). Orchestrator render cả
hai vào prompt synthesis. Cap số item bằng `graph_max_context_items` để khỏi phình prompt;
khi hybrid trả về, dedup item theo khóa cấu trúc: entity → `("entity", norm_name)`,
relation → `("relation", source_norm, keyword, target_norm)`.

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

> **⚠️ Bất đối xứng query ↔ document khi embed**: lúc index, chunk được embed bằng
> `embedding_text` (**có prepend heading context** — xem `vector_store.py`), còn query embed
> trần (chỉ câu hỏi). Dense retrieval thường chịu được asymmetry này, nhưng **phải đo** chứ
> không giả định. Bản đầu: giữ query trần (không bịa heading cho query). Đưa case này vào
> eval set (§Test plan); nếu recall kém, cân nhắc prepend một context tối thiểu vào query
> hoặc dùng instruction-style prompt theo đúng cách model `AITeamVN/Vietnamese_Embedding`
> được train. KHÔNG đổi cách embed document (sẽ phải re-index — ngoài scope).

## GraphRAG query-side

### Luồng

```text
question
  -> sinh mention (BƯỚC A: LLM hoặc token-match — xem Seed entity matching)
  -> ground mention -> norm_name (BƯỚC B: inverted-index + resolve alias)
  -> MATCH (:Entity {norm_name})
  -> expand 1-hop qua :REL
  -> collect node/edge source_chunk_ids        ──► RetrievalCandidate[]  (đường provenance)
  -> collect node/edge descriptions            ──► GraphContextItem[]    (content cho LLM)
  -> rank chunk ids
  -> return (candidates, graph_context)
```

`search_graph()` trả **cả hai**: `list[RetrievalCandidate]` (để RRF gộp với vector) và
`list[GraphContextItem]` (description đã chưng cất). Hybrid chuyển thẳng `graph_context` lên
`RetrievalResult`, không qua RRF (RRF chỉ xếp hạng chunk).

### Seed entity matching

Tách làm **2 bước** (đừng gộp): **A — sinh mention** (thực thể nào được nhắc trong câu) và
**B — grounding** (map mention → node `:Entity` thật trong KG). LLM chỉ thay được bước A;
bước B luôn cần (LLM không được tự đoán `norm_name`, sẽ bịa node không tồn tại → match rỗng).

> **KHÔNG dùng n-gram brute-force + Cypher exact-match** (loại 2026-06-26): sinh mọi n-gram
> 2-8 từ rồi bắn nhiều `MATCH` exact lên Neo4j vừa trượt nhiều (sai một chữ là miss) vừa đẩy
> ta sang `CONTAINS` full-scan.

#### Bước B — Grounding (LUÔN dùng, deterministic): `resolve()` trên mention GỐC (giữ dấu)

> **⚠️ Grounding luôn dùng tên CÓ DẤU — KHÔNG bỏ dấu.** `normalize_name()` hiện tại **giữ
> dấu** (docstring: "TUYỆT ĐỐI giữ dấu" — bỏ dấu làm "Quảng"≡"Quang", "Hòa"≡"Hỏa" sai nghĩa),
> và `alias_map` key theo `norm_name` **có dấu**. Vì vậy ground bằng đúng đường của indexing:
> `canonical_name, canonical_norm = resolve(mention)` — `resolve()` tự `normalize_name` (giữ
> dấu) + tra alias_map → đối xứng tuyệt đối với lúc index. Đây là chỗ **alias resolution
> query-side** phát huy — contribution của đồ án.
>
> **(MVP bỏ hẳn index không dấu.)** Đã cân nhắc thêm index bỏ dấu làm lưới đỡ khi user gõ
> thiếu dấu, nhưng **không làm cho MVP**: đường production trích mention bằng LLM (chiến lược
> 1) gần như luôn trả tên đúng chính tả có dấu, nên index không dấu thừa và còn dễ kéo theo
> đúng cái bug "bỏ dấu sai thứ tự làm alias miss". Nếu sau eval thấy user hay gõ thiếu dấu,
> thêm sau như một auxiliary key — luôn xác nhận lại bằng `norm_name` có dấu, không bao giờ
> làm đường khớp chính.

**Lúc khởi động** (cache lần đầu): load toàn bộ `norm_name` của `:Entity` từ Neo4j (KG nhỏ,
vài nghìn node) + alias map, kèm `source_count` mỗi entity (đo độ "hub"). Build **một index**:
`by_norm: dict[norm_name -> entity]` (key có dấu, đối xứng `resolve()`).

Cache ra `dataset/entity_index.json` (xem mục cache version ở §Config/cache bên dưới).

#### Bước A — Sinh mention: 2 chiến lược sau MỘT interface (injectable)

`graph_rag/retriever.py` nhận `seed_mentions: list[str] | None`. Nếu caller truyền sẵn → dùng;
nếu `None` → tự fallback chiến lược deterministic.

- **Chiến lược 1 — LLM extraction (đường PRODUCTION, ổn nhất cho tiếng Việt tự nhiên).**
  Orchestrator **đã** có 1 LLM call để rewrite standalone query (xem mục §5 + `orchestrator-plan.md`)
  → **gộp** entity extraction vào CHÍNH call đó bằng structured output, **zero latency thêm**:
  ```json
  { "standalone_query": "Điện Biên Phủ diễn ra như thế nào năm 1954?",
    "mentioned_entities": ["Điện Biên Phủ", "Võ Nguyên Giáp"] }
  ```
  Orchestrator truyền `mentioned_entities` xuống làm `seed_mentions`. LLM chỉ liệt kê thực thể
  **được nhắc tường minh** — KHÔNG suy diễn entity không có trong câu (câu kiểu "Ai lãnh đạo
  kháng chiến Nam Kỳ 1860?" không tên → để dense/vector lo, đừng ép LLM đoán → tránh bịa).
  Lý do né LLM trong plan gốc (sợ +1 call) **không còn**, vì gộp được vào call sẵn có.

- 🔴 **Chiến lược 2 đã XOÁ khỏi code (2026-08-03)** — `EntityIndex.token_match` không còn, và
  `match_seed_entities`/`search_graph` không còn nhận `query`. Lý do: nó chạy đúng lúc guard
  entity vừa loại sạch tên, tức âm thầm gỡ lại thứ guard vừa chặn theo một luật không kiểm
  soát được. Từ nay `entities` do node `plan` trích là nguồn seed duy nhất; rỗng = graph tắt
  cho query đó. Đoạn mô tả dưới giữ làm bản ghi lịch sử. Xem `agentic-retrieval-loop-plan.md`
  §2.1 (khối cảnh báo đầu mục).

- **Chiến lược 2 — Token-match deterministic (FALLBACK + BASELINE eval).** Khi `seed_mentions`
  là `None` (retrieval chạy standalone, debug, hoặc LLM lỗi): tokenize question → tra
  inverted-index trực tiếp, ưu tiên cụm khớp **nhiều token liên tiếp** (vd "điện biên phủ").
  Bắt buộc giữ vì: (a) cho `retrieve_graph(question)` chạy độc lập không cần LLM; (b) là
  **baseline tất định** để ablation "graph + seed deterministic" vs "graph + seed LLM" trong
  báo cáo; (c) lưới đỡ khi LLM fail.

#### Sort seed (sau grounding, chung cho cả 2 chiến lược)
Cụm dài hơn / khớp nhiều token trước; entity `source_count` thấp (ít hub) trước; cắt theo
`graph_max_seed_entities`.

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
def match_seed_entities(
    query: str, *, seed_mentions: list[str] | None = None, limit: int
) -> list[GraphSeed]:
    # seed_mentions != None  -> ground trực tiếp các mention (bước A chiến lược 1, từ LLM)
    # seed_mentions is None   -> token-match từ query (bước A chiến lược 2, fallback)
    ...

def search_graph(
    query: str, *, seed_mentions: list[str] | None = None, top_k: int | None = None
) -> tuple[list[RetrievalCandidate], list[GraphContextItem]]:
    ...  # trả CẢ candidate (provenance) LẪN graph_context (content)
```

Facade async giữ contract đồng nhất, `seed_mentions` là kwarg xuyên suốt:

```python
async def retrieve_graph(
    query: str, *, seed_mentions: list[str] | None = None
) -> RetrievalResult:
    ...
```

Có thể dùng Cypher 1-hop — `RETURN` cả `descriptions` của node/edge để dựng
`GraphContextItem`, không chỉ `source_chunk_ids`:

```cypher
MATCH (seed:Entity {norm_name: $norm_name})
OPTIONAL MATCH (seed)-[r:REL]-(neighbor:Entity)
RETURN seed.name, seed.descriptions, seed.source_chunk_ids,
       collect({keyword: r.keyword, descriptions: r.descriptions,
                source_chunk_ids: r.source_chunk_ids, neighbor: neighbor.name})
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

> **RRF chỉ dùng `rank`, KHÔNG dùng độ lớn score.** Vì vậy `graph_score` (tính từ
> seed hit / edge hit / hub penalty ở §GraphRAG) chỉ cần đủ để **sắp đúng thứ tự** rồi quy
> về rank — đừng over-engineer phần chấm điểm graph. Giữ `vector_score`/`graph_score` trên
> `RetrievedChunk` chỉ để debug/ablation. Nếu sau eval muốn graph signal mạnh hơn, dùng
> **weighted RRF** (`w_source / (k + rank)`) thay vì cố hòa hai thang đo gốc.

### Citation cho graph_context (tránh validator drop nguồn)

Vấn đề: LLM có thể dùng fact lấy từ `graph_context` (description của entity/relation), nhưng
`source_chunk_ids` của graph item đó **chưa chắc** nằm trong `result.chunks` (graph_context
KHÔNG qua RRF, còn chunks bị cắt `rerank_top_k`). Khi đó citation validator ở orchestrator
có thể **drop mất nguồn** vì không thấy chunk tương ứng → câu trả lời mất dẫn chứng dù fact đúng.

Chốt rule (chọn 1, mặc định **B**):

- **A. graph_context được phép sinh citation riêng.** Validator coi `source_chunk_ids` của
  graph item là nguồn hợp lệ ngang chunk. Đơn giản, không tốn hydrate thêm, nhưng citation
  trỏ tới chunk **không nằm trong context text** đưa cho LLM → khó cho user kiểm chứng.
- **B. Hybrid GẮN nguồn graph vào chunks (mặc định).** Trước khi hydrate, hybrid **union**
  `source_chunk_ids` của các `graph_context` item (cap nhỏ, vd ≤ `graph_max_context_items`)
  vào tập chunk_id sẽ hydrate — kể cả khi chúng không lọt top RRF. Như vậy mọi fact graph
  dùng đều có chunk tương ứng trong context → validator không drop. Đánh dấu các chunk này
  `sources=["graph"]` để phân biệt. Đây là lựa chọn nhất quán với "honest + có căn cứ".

Ghi rõ trong contract: nếu chọn B, `hybrid_candidate_k` chỉ cap phần RRF; chunk kéo theo từ
graph_context là **phần cộng thêm**, không bị cap đó cắt.

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
graph_max_context_items: int = 12   # cap GraphContextItem để khỏi phình prompt
```

Không thêm quá nhiều knob lúc đầu. Các giá trị này đủ để tune retrieval mà không làm config nở.

**Quan hệ các cap (tránh hiểu nhầm khi implement):** với graph, thứ tự áp dụng là
`graph_max_seed_entities` (cắt số seed) → `graph_max_chunks_per_seed` (cắt chunk MỖI seed)
→ gom + rank toàn bộ → `graph_top_k` (cắt cuối, đây là cap thắng). Tức `graph_top_k` là số
candidate graph THỰC SỰ trả ra; các cap kia chặn bùng nổ ở giữa. Tương tự,
`graph_max_context_items` cắt `graph_context` độc lập với `graph_top_k` (chunk và content
là hai trục riêng).

### Cache & version cho `entity_index.json` (BẮT BUỘC — nếu không sẽ bug khó nhìn)

`dataset/entity_index.json` ổn cho dev (khỏi query Neo4j mỗi lần khởi động), **nhưng phải
rebuild khi nguồn đổi**, nếu không sửa alias mà index cache cũ sẽ gây sai lệch âm thầm
(query khớp về canonical CŨ). Lưu **version stamp** trong file và rebuild khi lệch:

- `alias_map_version` — hash/mtime của `dataset/alias_map.json` (resolve dùng nó; nhớ
  `load_alias_map.cache_clear()` luôn nếu reload trong cùng process).
- `kg_version` — dấu hiệu KG đổi (vd số node `:Entity`, hoặc lần index gần nhất từ
  `run_graph_index.py`).

Lúc khởi động: nếu version trong cache ≠ version hiện tại → **rebuild từ Neo4j**, ghi đè
cache (atomic `os.replace`). `scripts/reset_stores.py` / re-index KG nên xoá hoặc làm mới
cache này. Đưa kiểm tra version vào unit test để khỏi quên.

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
- `test_graph_retrieval_collects_descriptions_into_graph_context`
- `test_graph_context_relation_keeps_structured_source_keyword_target`
- `test_hybrid_passes_graph_context_through_without_rrf`
- `test_grounding_resolves_alias_on_accented_mention` (alias có dấu khớp đúng canonical)
- `test_grounding_uses_inverted_index_not_per_phrase_cypher`
- `test_graph_retrieval_uses_injected_seed_mentions_when_provided`
- `test_graph_retrieval_falls_back_to_token_match_when_seed_mentions_none`
- `test_hybrid_hydrates_graph_context_source_chunks_for_citation` (rule B)
- `test_entity_index_rebuilds_when_alias_or_kg_version_changes`

### Integration tests optional

Đánh dấu skip nếu thiếu env hoặc backend remote:

- hỏi “Trương Định” phải có chunk liên quan.
- hỏi alias “Nguyễn Ái Quốc” phải match node/chunk canonical “Hồ Chí Minh” nếu graph đã index alias.
- hỏi quan hệ “Phan Bội Châu liên quan gì đến Cường Để?” hybrid phải có cả graph signal,
  text chunk **và** `graph_context` chứa cạnh quan hệ giữa hai người.

### Eval set ablation (bắt buộc để tune + bảo vệ đồ án)

Không tune được retrieval nếu không đo được, và muốn khẳng định "hybrid > traditional"
trước hội đồng thì phải có số. Soạn **30–50 câu hỏi** gán nhãn `expected_chunk_ids` (và với
câu quan hệ: cạnh KG kỳ vọng trong `graph_context`), phủ 4 nhóm:

- **factual** (mốc/sự kiện đơn) — kiểm tra dense.
- **quan hệ/nhân-quả** — kiểm tra graph + `graph_context`.
- **alias** (hỏi bằng tên gọi khác) — kiểm tra `resolve()` query-side.
- **ngoài domain / mơ hồ** — phải ra rỗng hoặc honest, không bịa.

Đo `recall@k` + `MRR` cho từng mode (`traditional` / `graph` / `hybrid`) → bảng ablation.
Đây cũng là dữ liệu để tune các knob (`rag_top_k`, `hybrid_rrf_k`, bật/tắt rerank,
asymmetry embedding ở §Traditional). Lưu eval set + script đo dưới `dataset/eval/`.

## Implementation order

1. Tạo `schemas/retrieval.py` (gồm `GraphContextItem` + `graph_context`).
2. Thêm config knobs (gồm `graph_max_context_items`).
3. Thêm `search_vector()` + tests mock Qdrant.
4. Build **bước B grounding**: inverted-index (load `norm_name`+alias từ Neo4j, cache
   `dataset/entity_index.json`) + `resolve()` + token-match fallback (bước A chiến lược 2) + tests.
5. Thêm graph query helpers (RETURN cả `descriptions`) + tests mock Neo4j/session.
6. Thêm `traditional_rag/retriever.py`.
7. Thêm `graph_rag/retriever.py` — nhận `seed_mentions` injectable, trả `(candidates, graph_context)`.
8. Thêm `hybrid/retriever.py`: RRF gộp chunk + hydrate once + chuyển thẳng `graph_context`.
   (Bước A chiến lược 1 — LLM extraction — hiện thực ở orchestrator, gộp vào call rewrite query.)
9. Thêm optional reranker.
10. Soạn eval set `dataset/eval/` + script đo recall@k/MRR cho 3 mode (ablation).
11. Chạy ruff/mypy/pytest; tune knob theo số đo eval.

## Acceptance criteria

- Có thể gọi:
  - `retrieve_traditional(question)`
  - `retrieve_graph(question)`
  - `retrieve_hybrid(question)`
- Hybrid là path mặc định cho orchestrator sau này.
- Mọi result có `chunk_id`, `text`, `metadata`, `heading_path`.
- Graph/hybrid result điền `graph_context` (entity/relation descriptions) khi match được;
  traditional để rỗng. `graph_context` đi thẳng, KHÔNG qua RRF.
- Seed matching tách bước A (sinh mention) / B (grounding); B dùng inverted-index + `resolve()`
  (không bắn Cypher exact-match per-phrase); `graph_rag` nhận `seed_mentions` injectable và
  fallback token-match khi `None`.
- Không có N+1 hydrate Postgres trong hybrid.
- Alias query-side dùng cùng `resolve()` với indexing.
- Empty retrieval không hallucinate; chỉ trả empty result cho tầng orchestrator xử lý.
- Unit tests cover core branching/error paths.
- Có eval set + bảng ablation recall@k cho 3 mode (để tune + bảo vệ đồ án).

## Handoff sang tầng trên (ghi để khỏi quên khi build orchestrator)

- **Seed extraction (bước A chiến lược 1)**: call LLM rewrite standalone query của
  orchestrator trả structured output `{standalone_query, mentioned_entities[]}`;
  orchestrator truyền `mentioned_entities` xuống `retrieve_graph/hybrid(..., seed_mentions=...)`.
  Nhờ gộp vào call sẵn có → không phát sinh LLM call riêng cho retrieval.
- **Visualization**: orchestrator lấy `[c.chunk_id for c in result.chunks]` truyền vào
  `build_visualization()` (xem `timeline-map-plan.md`). Retrieval KHÔNG gọi builder.
- **Synthesis**: orchestrator dựng prompt từ `result.chunks` (text + citation) **và**
  `result.graph_context` (quan hệ đã chưng cất) — hai khối riêng. Đây là chỗ graph-as-content
  phát huy ở câu quan hệ/nhân-quả.

