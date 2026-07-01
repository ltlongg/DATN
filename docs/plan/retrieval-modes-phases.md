# Retrieval Modes — Kế hoạch triển khai theo PHASE

> **Nguồn quyết định**: `docs/plan/retrieval-modes-plan.md` (đã chốt user 2026-07-01).
> File này chia plan đó thành 5 phase độc-lập-verify-được, mỗi phase có TDD + verification.
> **Sub-skill khi thực thi**: `superpowers:executing-plans` (inline, có checkpoint giữa phase).

**Goal**: Cho giáo viên CHỌN TAY 1 trong 3 mode (traditional / graph / hybrid) và nâng chất
lượng từng mode (BM25+rerank cho traditional, path-finding cho graph, 3-way RRF cho hybrid),
+ document reordering chung.

**Architecture**: Bồi đắp lên pipeline sẵn có (`orchestrator/nodes.retrieve` dispatch theo
`requested_mode`; 3 facade retriever đã tồn tại). Qdrant nhận thêm sparse vector `bm25`
(`Modifier.IDF`) qua fastembed client-side. Không viết lại, không thêm fallback thừa.

## Global Constraints (áp cho MỌI phase)

- **Stack có sẵn, KHÔNG code tay lại**: Qdrant Query API (RRF server-side), fastembed BM25,
  Neo4j Cypher `shortestPath`, Pydantic. Tra docs trước khi code (CLAUDE.md §Nguyên tắc).
- **Venv**: `.\venv\Scripts\python.exe` (root). Test agent: mock backend, KHÔNG chạm remote.
- **Lint/type/test mỗi phase**: `ruff check` + `mypy` + `pytest` phải xanh trước khi qua phase sau.
- **Tiếng Việt** cho comment/commit (theo phong cách repo).
- **KHÔNG làm** (chốt user): pre-filter metadata (B3); MMR/Dedup/Compression (F); auto
  `graph_empty_fallback`; rerank standalone graph.
- **Reindex tốn thời gian (local, không tốn API)**: chỉ chạy ở Phase 3, có verify riêng.
- **Không để rác**: file/test tạo ra mà không liên quan → xóa ngay trong phase đó.

---

## PHASE 1 — Plumbing chọn mode + graph-empty honest message

**Mục tiêu**: user gửi `mode` từ frontend → backend → agent → `nodes.retrieve` dispatch đúng
retriever; `retrieval_mode` trả về phản ánh mode đã chọn. Graph mode không ground được seed →
trả lời honest gợi ý đổi mode (KHÔNG auto-fallback).

**Files**:
- Modify: `apps/agent-service/app/schemas/ask.py` (AskRequest.mode, AskResponse.retrieval_mode)
- Modify: `apps/agent-service/app/orchestrator/state.py` (requested_mode + widen retrieval_mode)
- Modify: `apps/agent-service/app/orchestrator/runner.py` (initial_state set requested_mode + build_response)
- Modify: `apps/agent-service/app/orchestrator/nodes.py` (retrieve dispatch + honest_answer message)
- Modify: `apps/backend/app/schemas/chat.py` (AskRequest.mode)
- Modify: `apps/backend/app/services/agent_client.py` (AgentAskRequest.mode)
- Modify: `apps/backend/app/api/chat.py` (truyền body.mode)
- Test: `apps/agent-service/tests/test_orchestrator_flow.py` (dispatch 3 mode + graph-empty msg)
- Test: `apps/backend/tests/test_chat_stream.py` (mode proxy)

**Interfaces produced**:
- `AskRequest.mode: RetrievalMode = "hybrid"` (RetrievalMode = `Literal["traditional","graph","hybrid"]`, import từ `schemas/retrieval.py`).
- `AgentState["requested_mode"]: RetrievalMode`; `AgentState["retrieval_mode"]: Literal["traditional","graph","hybrid","none"]`.
- `nodes.GRAPH_EMPTY_MESSAGE: str`.

### Thiết kế chốt (giữ đơn giản)
- `retrieve()` set `retrieval_mode = requested_mode` LUÔN (kể cả khi rỗng) → response trung thực mode.
- Graph-empty message: KHÔNG thêm state field mới. `honest_answer` suy từ state:
  `requested_mode == "graph"` AND `retrieval is not None` AND `not retrieval.chunks`
  → dùng `GRAPH_EMPTY_MESSAGE`. Các trường hợp honest khác (out_of_scope route → retrieval None;
  citation fail → retrieval.chunks non-empty) giữ `HONEST_MESSAGE` cũ. Điều kiện này phân biệt
  chính xác, không đụng nhánh khác.
- traditional/hybrid rỗng → vẫn `HONEST_MESSAGE` (user chỉ yêu cầu graph-specific).

### Code chính

`schemas/ask.py`:
```python
from app.schemas.retrieval import RetrievalMode  # thêm import
# AskRequest:
    mode: RetrievalMode = "hybrid"
# AskResponse:
    retrieval_mode: Literal["traditional", "graph", "hybrid", "none"] = "none"
```

`state.py`:
```python
from app.schemas.retrieval import RetrievalMode, RetrievalResult
    requested_mode: RetrievalMode
    retrieval_mode: Literal["traditional", "graph", "hybrid", "none"]
```

`runner.py::initial_state`: thêm `"requested_mode": request.mode,` (giữ `"retrieval_mode": "none"`).
`build_response` không đổi (đã đọc `state.get("retrieval_mode","none")`); chỉ widen type khớp.

`nodes.py::retrieve` (thay thân hàm, giữ chữ ký):
```python
from app.tools.traditional_rag.retriever import retrieve_traditional
from app.tools.graph_rag.retriever import retrieve_graph
# (giữ retrieve_hybrid)

async def retrieve(state, config):
    emitter = _emitter(config)
    mode = state["requested_mode"]
    await emitter.emit("status", {"node": "retrieve", "msg": f"đang tìm tài liệu ({mode})"})
    if mode == "traditional":
        result = await retrieve_traditional(state["standalone_query"])
    elif mode == "graph":
        result = await retrieve_graph(state["standalone_query"], seed_mentions=state["seed_mentions"])
    else:
        result = await retrieve_hybrid(state["standalone_query"], seed_mentions=state["seed_mentions"])
    return {
        "retrieval": result,
        "retrieval_mode": mode,
        "warnings": result.warnings,
        "debug": {"retrieve": {"mode": mode, "chunks": len(result.chunks),
                               "graph_context": len(result.graph_context)}},
    }
```

`nodes.py::honest_answer` — chọn message:
```python
GRAPH_EMPTY_MESSAGE = (
    "Mình chưa tìm thấy thực thể hoặc quan hệ phù hợp trong knowledge graph cho câu hỏi này "
    "ở chế độ Graph. Bạn thử lại bằng chế độ Traditional hoặc Hybrid để tìm theo nội dung "
    "tài liệu nhé."
)

def _honest_message(state) -> str:
    retrieval = state.get("retrieval")
    if state.get("requested_mode") == "graph" and retrieval is not None and not retrieval.chunks:
        return GRAPH_EMPTY_MESSAGE
    return HONEST_MESSAGE
# trong honest_answer: text = _honest_message(state); emit + return text thay vì HONEST_MESSAGE cứng.
```

Backend `schemas/chat.py::AskRequest`: thêm `mode: Literal["traditional","graph","hybrid"] = "hybrid"`.
Backend `agent_client.py::AgentAskRequest`: thêm `mode: Literal[...] = "hybrid"` (đã `model_dump()` vào payload → tự truyền).
Backend `api/chat.py::ask`: `AgentAskRequest(..., mode=body.mode)`.

### Tasks (TDD)
- [ ] **1.1** Test: 3 case `test_dispatch_mode_calls_correct_retriever` trong test_orchestrator_flow.py — mock `retrieve_traditional`/`retrieve_graph`/`retrieve_hybrid`, gửi `AskRequest(question=..., mode=m, stream=False)`, assert đúng retriever được gọi + `resp.retrieval_mode == m`.
- [ ] **1.2** Test: `test_graph_empty_suggests_other_mode` — mode=graph, retrieve trả `RetrievalResult(mode="graph", chunks=[])` → `resp.answer` chứa "Traditional" và "Hybrid"; mode=traditional rỗng → vẫn message cũ ("chưa tìm thấy đủ thông tin").
- [ ] **1.3** Chạy test → FAIL (mode chưa tồn tại). Implement schemas/state/runner/nodes. Chạy lại → PASS.
- [ ] **1.4** Backend test: `test_ask_forwards_mode` — POST `/ask` với `{"question":..,"mode":"graph"}`, assert MockTransport nhận payload `mode="graph"`. Implement backend 3 file. PASS.
- [ ] **1.5** `ruff` + `mypy` + cả 2 test suite xanh. Commit.

### Verification Phase 1
- `pytest apps/agent-service/tests/test_orchestrator_flow.py apps/backend/tests/test_chat_stream.py -v`
- Trace tay: đọc lại `nodes.retrieve` — 3 nhánh đúng retriever, `retrieval_mode` set mọi nhánh.
- Mặc định `mode="hybrid"` → hành vi CŨ không đổi (regression: toàn bộ test_orchestrator_flow cũ vẫn xanh vì default hybrid).

---

## PHASE 2 — Graph path-finding (giá trị cao nhất, contribution)

**Mục tiêu**: graph mode (và hybrid kế thừa) trả lời được câu hỏi *quan hệ giữa ≥2 thực thể*
bằng `shortestPath` từng cặp seed. KHÔNG rerank standalone graph (giữ nguyên — decision 4).

**Files**:
- Modify: `apps/agent-service/app/core/config.py` (graph_max_path_hops, graph_path_hit_weight)
- Modify: `apps/agent-service/app/tools/graph_rag/graph_store.py` (Cypher path + tích hợp vào search_graph)
- Test: `apps/agent-service/tests/test_graph_search.py` (path-finding cases)

**Interfaces produced**: `search_graph` vẫn trả `tuple[list[RetrievalCandidate], list[GraphContextItem]]` — nhưng candidate/context giàu thêm node+relation trên path (không đổi chữ ký → hybrid tự kế thừa).

### Thiết kế chốt (giữ đơn giản, chống bùng nổ)
- Kích hoạt khi `len(seeds) >= 2`. Số cặp = C(n,2), cap seed=5 → tối đa 10 cặp. `shortestPath`
  = 1 đường/cặp → chặn cứng, không bùng nổ.
- `{MAXHOP}` = `graph_max_path_hops` (mặc định 3): nội suy int đã validate vào chuỗi Cypher
  (Neo4j không parametrize var-length; cùng lý do file này không parametrize label/rel-type).
  MAXHOP là hằng config, KHÔNG input user → an toàn. `assert isinstance(maxhop, int)` trước nội suy.
- Node trên path → `GraphContextItem(kind="entity")`; relation trên path → `kind="relation"`
  (hướng thật startNode/endNode). Dedup tái dùng `dedup_key()` (không trùng phần 1-hop).
- Chunk trên path → `_bump` với trọng số `_PATH_HIT = graph_path_hit_weight` (1.5). Dùng một
  `counted` set CHUNG cho path (không per-seed) để cap tổng, tránh đếm trùng.
- Không có đường nối cặp đó → bỏ qua (honest, không bịa). KHÔNG raise.

### Code chính
`config.py`: `graph_max_path_hops: int = 3`, `graph_path_hit_weight: float = 1.5`.

`graph_store.py` — thêm hằng + Cypher:
```python
_PATH_HIT = 1.5  # default; lấy từ settings.graph_path_hit_weight lúc chạy

def _path_cypher(max_hop: int) -> str:
    assert isinstance(max_hop, int) and max_hop >= 1  # chặn injection: chỉ int
    return f"""
    MATCH path = shortestPath(
      (a:Entity {{norm_name: $a}})-[:REL*1..{max_hop}]-(b:Entity {{norm_name: $b}})
    )
    RETURN [n IN nodes(path) | {{name: n.name, norm: n.norm_name,
                                descriptions: n.descriptions, chunks: n.source_chunk_ids}}] AS nodes,
           [r IN relationships(path) | {{keyword: r.keyword, descriptions: r.descriptions,
                                         chunks: r.source_chunk_ids,
                                         src_name: startNode(r).name, src_norm: startNode(r).norm_name,
                                         tgt_name: endNode(r).name, tgt_norm: endNode(r).norm_name}}] AS rels
    """
```
Trong `search_graph`, SAU vòng 1-hop, nếu `len(seeds) >= 2`:
```python
import itertools
path_counted: set[str] = set()
path_weight = settings.graph_path_hit_weight
cypher = _path_cypher(settings.graph_max_path_hops)
for a, b in itertools.combinations(seeds, 2):
    rec = session.run(cypher, a=a.info.norm_name, b=b.info.norm_name).single()
    if rec is None:
        continue
    for node in rec["nodes"] or []:
        context.append(GraphContextItem(kind="entity", name=node["name"], norm_name=node["norm"],
            description=_join_descriptions(node["descriptions"]),
            source_chunk_ids=list(node["chunks"] or [])[:per_seed_cap],
            matched_seed=f"{a.mention}↔{b.mention}"))
        for cid in node["chunks"] or []:
            _bump(cid, path_weight, f"{a.mention}↔{b.mention}", path_counted)
    for rel in rec["rels"] or []:
        if not rel or not rel.get("keyword"):
            continue
        rel_chunks = list(rel["chunks"] or [])
        context.append(GraphContextItem(kind="relation", source_name=rel["src_name"],
            source_norm=rel["src_norm"], target_name=rel["tgt_name"], target_norm=rel["tgt_norm"],
            keyword=rel["keyword"], description=_join_descriptions(rel["descriptions"]),
            source_chunk_ids=rel_chunks[:per_seed_cap], matched_seed=f"{a.mention}↔{b.mention}"))
        for cid in rel_chunks:
            _bump(cid, path_weight, f"{a.mention}↔{b.mention}", path_counted)
```
> Lưu ý: `_bump` hiện cap theo `counted` truyền vào; path dùng `path_counted` riêng để cap tổng
> chunk path. Vòng for cặp nằm TRONG `with driver.session()` đang mở (tái dùng session).

### Tasks (TDD)
- [ ] **2.1** Test `test_search_graph_pathfinding_two_seeds` — fake driver trả record cho `_path_cypher` (cần `_Session.run` phân biệt cypher path vs expand theo `**kwargs` có `a`/`b`). 2 seed → context có relation nối a→b, candidate có chunk trên path.
- [ ] **2.2** Test `test_search_graph_no_path_skips_pair` — path record None → không thêm gì, không raise.
- [ ] **2.3** Test `test_search_graph_single_seed_no_pathfinding` — 1 seed → KHÔNG gọi path cypher (giữ 1-hop cũ).
- [ ] **2.4** Test `test_path_cypher_rejects_non_int` — `_path_cypher("3; DROP")` raise AssertionError.
- [ ] **2.5** Run → FAIL → implement → PASS. Cập nhật `_Session` fake để route theo cypher. Đảm bảo test_graph_search cũ vẫn xanh.
- [ ] **2.6** `ruff` + `mypy` + pytest xanh. Commit.

### Verification Phase 2
- Unit xanh + regression test cũ xanh.
- Trace: combinations đúng cap (n≤5 → ≤10 cặp); `path_counted` riêng; dedup_key chống trùng.
- (Tay, optional sau khi có data) chạy agent gọi `/ask mode=graph` câu "Quan hệ giữa Phan Bội
  Châu và Phan Châu Trinh?" → `graph_context` có relation nối hai entity.

---

## PHASE 3 — Traditional: dense + BM25 (RRF server-side) + rerank + reindex

**Mục tiêu**: traditional = dense + sparse BM25 fuse trong Qdrant (Query API RRF) rồi rerank.
Cần reindex Qdrant sạch (dense+sparse). Postgres/Neo4j giữ nguyên.

**Files**:
- Modify: `apps/agent-service/requirements.txt` (+ `fastembed`)
- Modify: `apps/agent-service/app/core/config.py` (bm25_model, bm25_top_k, sparse_vector_name)
- Create: `apps/agent-service/app/core/sparse.py` (BM25 encode helpers, lazy-load như reranker)
- Modify: `apps/agent-service/app/core/qdrant.py` (ensure_chunks_collection thêm sparse config)
- Modify: `apps/agent-service/app/tools/graph_rag/vector_store.py` (upsert đính sparse + `search_dense_sparse`)
- Modify: `apps/agent-service/app/tools/traditional_rag/retriever.py` (dùng search_dense_sparse + rerank)
- Create: `apps/agent-service/tests/test_sparse.py`
- Modify: `apps/agent-service/tests/test_traditional_retriever.py`

**Interfaces produced**:
- `app.core.sparse.encode_documents(texts) -> list[tuple[list[int], list[float]]]` (indices, values).
- `app.core.sparse.encode_query(text) -> tuple[list[int], list[float]]`.
- `vector_store.search_dense_sparse(query, *, top_k=None, client=None) -> list[RetrievalCandidate]` (source="vector", fused RRF server-side).

### Thiết kế chốt
- **fastembed client-side** (`SparseTextEmbedding("Qdrant/bm25")`): deterministic, mock được.
  `Modifier.IDF` bật ở collection (fastembed bm25 cố ý bỏ IDF → phải để Qdrant tính).
- Dense GIỮ unnamed (default) → `search_vector` cũ KHÔNG vỡ (hybrid Phase 4 vẫn xài). Sparse
  named `"bm25"`.
- `upsert_chunk_vectors`: point vector = `{"": dense_list, "bm25": SparseVector(indices, values)}`.
  **VERIFY cú pháp** key `""` cho unnamed dense (xem verify step — nếu sai, dùng `models.Vector`/named).
- traditional fuse SERVER-SIDE (1 call Query API, Qdrant tự RRF) — đơn giản hơn client RRF, vì
  traditional không cần trộn graph. Hybrid (Phase 4) mới fuse client-side (vì có graph).
- candidate fused gắn `source="vector"` (không tách được dense/sparse sau fusion; sources=["vector"]).

### Code chính
`sparse.py` (pattern lazy-load + Lock như reranker.py):
```python
from threading import Lock
_model = {}
_lock = Lock()
def _get():
    if "m" not in _model:
        with _lock:
            if "m" not in _model:
                from fastembed import SparseTextEmbedding
                _model["m"] = SparseTextEmbedding(get_settings().bm25_model)
    return _model["m"]

def encode_documents(texts):
    embs = list(_get().embed(texts))            # SparseEmbedding: .indices .values
    return [(e.indices.tolist(), e.values.tolist()) for e in embs]

def encode_query(text):
    e = next(iter(_get().query_embed(text)))    # query_embed: BM25 query (không TF weight)
    return e.indices.tolist(), e.values.tolist()
```

`config.py`:
```python
bm25_model: str = "Qdrant/bm25"
bm25_top_k: int = 20
sparse_vector_name: str = "bm25"
```

`qdrant.py::ensure_chunks_collection`:
```python
from qdrant_client.models import SparseVectorParams, Modifier
client.create_collection(
    collection_name=name,
    vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
    sparse_vectors_config={get_settings().sparse_vector_name: SparseVectorParams(modifier=Modifier.IDF)},
)
```

`vector_store.py::upsert_chunk_vectors` — thêm sparse vào point:
```python
from qdrant_client.models import SparseVector
from app.core.sparse import encode_documents
# trong vòng batch: sparse = encode_documents(texts)  # cùng thứ tự texts
points = [PointStruct(id=point_id_for(r["chunk_id"]), payload=_payload(r),
            vector={"": vec.tolist(), name: SparseVector(indices=si, values=sv)})
          for r, vec, (si, sv) in zip(batch, vectors, sparse)]
# name = get_settings().sparse_vector_name
```

`vector_store.py::search_dense_sparse` (mới):
```python
from qdrant_client.models import Prefetch, FusionQuery, Fusion, SparseVector
async def search_dense_sparse(query, *, top_k=None, client=None):
    settings = get_settings()
    k = top_k or settings.rag_top_k
    try:
        dense = (await embed_texts([query]))[0].tolist()
    except Exception as exc:
        raise RetrievalBackendError("embedding_failed") from exc
    si, sv = await asyncio.to_thread(encode_query, query)
    try:
        client = client or get_qdrant_client()
        resp = await asyncio.to_thread(client.query_points,
            collection_name=settings.qdrant_collection,
            prefetch=[Prefetch(query=dense, limit=settings.rag_top_k),
                      Prefetch(query=SparseVector(indices=si, values=sv),
                               using=settings.sparse_vector_name, limit=settings.bm25_top_k)],
            query=FusionQuery(fusion=Fusion.RRF), limit=k, with_payload=True)
    except Exception as exc:
        raise RetrievalBackendError("qdrant_unavailable") from exc
    cands = []
    for p in resp.points:
        cid = (p.payload or {}).get("chunk_id")
        if not cid: continue
        cands.append(RetrievalCandidate(chunk_id=str(cid), source="vector",
                                        rank=len(cands)+1, score=p.score))
    return cands
```

`traditional_rag/retriever.py`:
```python
from app.tools.graph_rag.vector_store import search_dense_sparse  # thay search_vector
from app.core.reranker import rerank
# candidates = await search_dense_sparse(question, top_k=top_k)
# ... hydrate như cũ ...
# trước return: chunks = await rerank(question, chunks); chunks = chunks[:settings.rerank_top_k]
```

### Tasks (TDD)
- [ ] **3.1** `pip install fastembed` vào root venv; thêm vào requirements.txt. Verify import.
- [ ] **3.2** test_sparse.py: `test_encode_query_returns_indices_values` (chạy thật fastembed bm25 trên 1 câu tiếng Việt ngắn → indices/values non-empty, cùng độ dài). (1 test nhẹ, không mock — model nhỏ.)
- [ ] **3.3** test_traditional_retriever.py: đổi mock `search_vector`→`search_dense_sparse`; thêm `test_traditional_calls_rerank_and_cuts` (mock rerank đảo thứ tự + cut rerank_top_k). Run → FAIL.
- [ ] **3.4** Implement config + sparse.py + qdrant.py + vector_store (upsert+search_dense_sparse) + retriever. Run → PASS.
- [ ] **3.5** `ruff`+`mypy`+pytest agent xanh. Commit code (CHƯA reindex).
- [ ] **3.6** **Reindex** (verify riêng — xem dưới). Commit ghi chú reindex nếu cần.

### Verification Phase 3 (gồm reindex — bước cẩn trọng)
1. Unit xanh: `pytest apps/agent-service/tests/test_sparse.py apps/agent-service/tests/test_traditional_retriever.py -v`.
2. **Smoke 1 chunk TRƯỚC khi reindex toàn bộ**: viết script tạm trong scratchpad upsert 1 record
   thật rồi `client.scroll(collection, with_vectors=True, limit=1)` → xác nhận point có CẢ dense
   (key `""`) lẫn `bm25` sparse. **Đây là chỗ verify cú pháp key `""`.** Nếu sai cú pháp → sửa
   `upsert_chunk_vectors` trước khi reindex full. Xóa script tạm sau khi xong.
3. Reindex sạch: `reset_stores.py --yes` (drop collection — Postgres/Neo4j cũng drop! → CHỈ
   muốn drop Qdrant). ⚠️ **reset_stores xóa cả 3 store** → KHÔNG dùng full. Thay vào đó chỉ
   recreate Qdrant collection: `python -c "from app.core.qdrant import get_qdrant_client, ensure_chunks_collection; c=get_qdrant_client(); c.delete_collection('history_vn_chunks'); ensure_chunks_collection()"`
   rồi `run_graph_index.py --limit -1 --skip-graph` (Postgres rag_chunks đã có → upsert lại vector dense+sparse, bỏ graph).
4. Set `.env`: `RERANKER_MODEL=AITeamVN/Vietnamese_Reranker`.
5. Trace: gọi `/ask mode=traditional` 1 câu keyword-nặng (vd tên riêng) → kết quả có chunk khớp keyword (BM25 đóng góp); so với chỉ-dense trước đó.

> **Quyết định cần xác nhận khi tới Phase 3**: reset_stores.py drop cả 3 store. Plan gốc B1 ghi
> "Postgres+Neo4j giữ nguyên". Nên reindex Qdrant-only bằng lệnh recreate collection ở trên,
> KHÔNG chạy `reset_stores.py`. (Ghi chú để khỏi xoá nhầm.)

---

## PHASE 4 — Hybrid 3-way (dense + sparse BM25 + graph)

**Mục tiêu**: hybrid thêm nguồn sparse BM25 vào RRF (đang 2 nguồn → 3). Path-finding + rerank
hybrid tự kế thừa (đã có).

**Files**:
- Modify: `apps/agent-service/app/schemas/retrieval.py` (CandidateSource + "sparse")
- Modify: `apps/agent-service/app/tools/graph_rag/vector_store.py` (search_bm25 primitive)
- Modify: `apps/agent-service/app/tools/hybrid/retriever.py` (3-way gather + RRF + _SOURCE_ORDER)
- Modify: `apps/agent-service/tests/test_hybrid_retriever.py`

**Interfaces produced**:
- `CandidateSource = Literal["vector", "graph", "sparse"]`.
- `vector_store.search_bm25(query, *, top_k=None, client=None) -> list[RetrievalCandidate]` (source="sparse", sparse-only).

### Thiết kế chốt
- `search_bm25`: query_points `using="bm25"` (sparse-only, KHÔNG fusion) → candidate source="sparse".
- hybrid: thêm `_bm25_candidates()` vào `asyncio.gather` (song song vector+graph). RRF loop đổi
  `[*vec_cands, *graph_cands]` → `[*vec_cands, *bm25_cands, *graph_cands]` (loop đã generalize).
- `_SOURCE_ORDER = {"vector":0, "sparse":1, "graph":2}`.
- Nguồn sparse chết → warning + degrade (KHÔNG raise nếu còn nguồn khác). Cả ba chết → vẫn raise
  `all_backends_failed` (giữ logic: vec_err và graph_err; sparse coi như phụ của vector store —
  nếu vector sống thì sparse thường cũng sống; nếu sparse chết riêng chỉ warning).
- `vector_score`/`sparse_score`: tùy chọn — KHÔNG thêm field mới nếu không cần (giữ đơn giản;
  sparse candidate score vào debug). `RetrievedChunk` không thêm sparse_score (YAGNI).

### Code chính
`retrieval.py`: `CandidateSource = Literal["vector", "graph", "sparse"]`.

`vector_store.py::search_bm25`:
```python
async def search_bm25(query, *, top_k=None, client=None):
    settings = get_settings()
    k = top_k or settings.bm25_top_k
    si, sv = await asyncio.to_thread(encode_query, query)
    try:
        client = client or get_qdrant_client()
        resp = await asyncio.to_thread(client.query_points,
            collection_name=settings.qdrant_collection,
            query=SparseVector(indices=si, values=sv),
            using=settings.sparse_vector_name, limit=k, with_payload=True)
    except Exception as exc:
        raise RetrievalBackendError("qdrant_unavailable") from exc
    cands = []
    for p in resp.points:
        cid = (p.payload or {}).get("chunk_id")
        if not cid: continue
        cands.append(RetrievalCandidate(chunk_id=str(cid), source="sparse",
                                        rank=len(cands)+1, score=p.score))
    return cands
```

`hybrid/retriever.py`:
```python
_SOURCE_ORDER = {"vector": 0, "sparse": 1, "graph": 2}

async def _bm25_candidates(question):
    try:
        return await search_bm25(question), None
    except RetrievalBackendError as exc:
        return [], exc

# trong retrieve_hybrid:
(vec_cands, vec_err), (bm25_cands, bm25_err), (graph_cands, graph_context, graph_err) = \
    await asyncio.gather(_vector_candidates(question), _bm25_candidates(question),
                         _graph_candidates(question, seed_mentions))
if vec_err is not None and graph_err is not None:
    raise RetrievalBackendError("all_backends_failed")
# warnings: thêm bm25_err -> "sparse backend lỗi (...), bỏ qua."
# RRF loop: for cand in [*vec_cands, *bm25_cands, *graph_cands]:
#   nhánh score: vector->vector_score, graph->graph_score, sparse-> (bỏ vào debug, không field riêng)
```
> RRF loop hiện gán `vector_score`/`graph_score` theo `cand.source`. Thêm nhánh `sparse`: KHÔNG
> set field (giữ schema), chỉ cộng rrf_score + add source. `_build` đã sort sources theo `_SOURCE_ORDER`.

### Tasks (TDD)
- [ ] **4.1** Test `test_hybrid_3way_rrf` — vector+sparse+graph cùng trỏ 1 chunk → rrf cao nhất, sources gồm cả 3. Mock `search_bm25` trong H.
- [ ] **4.2** Test `test_hybrid_degrades_when_sparse_fails` — bm25 raise → warning "sparse", vẫn trả chunk từ vector/graph.
- [ ] **4.3** Test regression: các test_hybrid cũ phải patch thêm `search_bm25` (mặc định trả []). Cập nhật `_patch` helper.
- [ ] **4.4** Run → FAIL → implement schemas + search_bm25 + hybrid → PASS.
- [ ] **4.5** `ruff`+`mypy`+pytest xanh. Commit.

### Verification Phase 4
- Unit 3-way xanh + regression hybrid cũ xanh.
- Trace: `_SOURCE_ORDER` có "sparse"; gather 3 nhánh; degrade đúng.
- (Tay, cần reindex Phase 3 xong) `/ask mode=hybrid` so chất lượng với traditional/graph.

---

## PHASE 5 — Document Reordering (chống "lost in the middle"), áp chung 3 mode

**Mục tiêu**: trước synthesize, xếp chunk điểm cao ra ĐẦU và CUỐI context, chunk yếu vào giữa.
Thuần sắp xếp, KHÔNG gọi LLM, KHÔNG bỏ chunk. (Mục DUY NHẤT của Phần F — chốt user.)

**Files**:
- Create: `apps/agent-service/app/tools/reorder.py`
- Modify: `apps/agent-service/app/orchestrator/nodes.py` (synthesize: reorder trước build_user_prompt)
- Create: `apps/agent-service/tests/test_reorder.py`

**Interfaces produced**: `app.tools.reorder.reorder_for_context(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]`.

### Thiết kế chốt
- Input: chunks đã sắp best-first (rerank/graph-score/RRF đã làm). Output: best xen kẽ về 2 đầu.
- Thuật toán kinh điển (LangChain LongContextReorder): index chẵn dồn về đầu (giữ thứ tự),
  index lẻ về cuối (đảo) → best ở đầu, 2nd-best ở cuối, yếu nhất giữa.
- Đặt trong `synthesize` (altitude đúng: chỉ ảnh hưởng layout prompt, KHÔNG đổi `retrieval.chunks`
  lưu ở state, KHÔNG đụng citations/visualization). Pure function → dễ test.

### Code chính
`reorder.py`:
```python
from app.schemas.retrieval import RetrievedChunk
def reorder_for_context(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Best-first -> best ở hai đầu, yếu ở giữa (lost-in-the-middle)."""
    head, tail = [], []
    for i, c in enumerate(chunks):
        (head if i % 2 == 0 else tail).append(c)
    return head + tail[::-1]
```
`nodes.py::synthesize`: `chunks_for_prompt = reorder_for_context(retrieval.chunks)` rồi truyền vào
`syn_prompt.build_user_prompt(state["standalone_query"], chunks_for_prompt, retrieval.graph_context, ...)`.

### Tasks (TDD)
- [ ] **5.1** Test `test_reorder_best_at_ends` — input [c0..c4] (best-first) → output[0]==c0, output[-1]==c1, c4 ở giữa. `test_reorder_empty`/`test_reorder_single` → trả nguyên.
- [ ] **5.2** Test `test_synthesize_reorders_chunks` — mock stream_synthesis capture chunks order trong prompt; verify reorder áp dụng. (Hoặc kiểm gián tiếp qua build_user_prompt.)
- [ ] **5.3** Run → FAIL → implement reorder.py + sửa synthesize → PASS.
- [ ] **5.4** `ruff`+`mypy`+pytest xanh. Commit.

### Verification Phase 5
- Unit xanh; regression test_orchestrator_flow xanh (reorder trong suốt với citations/viz).
- Trace: reorder pure, không mất chunk (len giữ nguyên), không đụng state.retrieval.

---

## Self-review (spec coverage)
- A (plumbing) → Phase 1 ✓ | B (traditional BM25+rerank) → Phase 3 ✓ | C2 (path-finding) → Phase 2 ✓ |
  C3 (graph-empty honest) → Phase 1 ✓ | C4 (không rerank graph) → giữ nguyên (retrieve_graph đã
  không rerank) ✓ | D (hybrid 3-way) → Phase 4 ✓ | E (config) → rải Phase 2/3 ✓ |
  F (chỉ Document Reordering) → Phase 5 ✓.
- KHÔNG làm: B3 pre-filter, MMR/Dedup/Compression, graph_empty_fallback — không có task nào.

## Thứ tự thực thi
Phase 1 → 2 → 3 (gồm reindex) → 4 → 5. Mỗi phase: TDD → ruff/mypy/pytest → verify → commit →
checkpoint với user trước khi qua phase sau (nhất là Phase 3 reindex).
