# Plan: 3 retrieval mode (traditional / graph / hybrid) + cải tiến chất lượng

## Context — vì sao làm

Hiện `nodes.retrieve()` **hardcode** gọi `retrieve_hybrid` và set `retrieval_mode="hybrid"`
cứng. Người dùng (giáo viên) không chọn được cách truy hồi. Yêu cầu: cho người dùng **tự
chọn 1 trong 3 mode** (không để LLM đoán ý định), đồng thời **nâng chất lượng từng mode**:

- **Traditional** hiện chỉ là dense vector thuần → yếu, không tận dụng keyword lẫn rerank.
- **Graph** hiện chỉ expand 1-hop độc lập mỗi seed → không trả lời được câu hỏi *quan hệ
  giữa các thực thể* (vốn là lý do tồn tại của graph mode).
- **Hybrid** cần kế thừa các cải tiến trên để vẫn là "bản tốt nhất của cả hai".

Hạ tầng đã sẵn: cả 3 facade retriever đã tồn tại (`retrieve_traditional/graph/hybrid`),
reranker đã wire trong hybrid, RRF loop đã generalize cho N nguồn. Qdrant **server 1.18.2 /
client 1.18.0** hỗ trợ sparse vector + `Modifier.IDF`. Đây là thay đổi *bồi đắp*, không
viết lại.

---

## Quyết định đã CHỐT (user 2026-07-01)

1. **Pre-filter metadata (Phần B3): TUYỆT ĐỐI KHÔNG LÀM** ở giai đoạn này. Có thể xem lại
   sau nếu có thời gian — không thì thôi. Để metadata cho rerank xử lý gián tiếp.
2. **Phần F — Kỹ thuật RAG khác: CHỈ làm `Document Reordering`.** Các kỹ thuật khác (MMR,
   Context Deduplication, ...) **KHÔNG làm**.
3. **Graph không ground được seed: KHÔNG auto-fallback** sang vector (`graph_empty_fallback`
   bị bỏ). Thay vào đó **trả lời honest cho user**: không tìm thấy nội dung phù hợp ở chế độ
   Graph, hãy thử mode khác.
4. **KHÔNG rerank cho standalone graph** — giữ nguyên thứ tự theo graph score.

---

## Phần A — Cho người dùng chọn mode (plumbing)

Luồng: `frontend → backend /ask → agent /ask → orchestrator state → node retrieve`.

| File | Thay đổi |
|---|---|
| `apps/agent-service/app/schemas/ask.py` | `AskRequest`: thêm `mode: RetrievalMode = "hybrid"` (import `RetrievalMode` từ `schemas/retrieval.py`). `AskResponse.retrieval_mode`: nới `Literal["hybrid","none"]` → `Literal["traditional","graph","hybrid","none"]` |
| `apps/agent-service/app/orchestrator/state.py` | Thêm field `requested_mode: RetrievalMode`; nới `retrieval_mode` như trên |
| `apps/agent-service/app/orchestrator/runner.py` | `initial_state()`: set `"requested_mode": request.mode`, `"retrieval_mode": "none"` |
| `apps/agent-service/app/orchestrator/nodes.py` | `retrieve()`: **dispatch** theo `state["requested_mode"]` (xem dưới); set `retrieval_mode = requested_mode` |
| `apps/backend/app/schemas/chat.py` | `AskRequest`: thêm `mode: Literal["traditional","graph","hybrid"] = "hybrid"` |
| `apps/backend/app/services/agent_client.py` | `AgentAskRequest`: thêm `mode`; truyền vào payload gửi agent |
| `apps/backend/app/api/chat.py` | `ask()`: truyền `body.mode` vào `AgentAskRequest` |

`nodes.retrieve()` dispatch:
```python
mode = state["requested_mode"]
if mode == "traditional":
    result = await retrieve_traditional(state["standalone_query"])
elif mode == "graph":
    result = await retrieve_graph(state["standalone_query"], seed_mentions=state["seed_mentions"])
else:  # hybrid
    result = await retrieve_hybrid(state["standalone_query"], seed_mentions=state["seed_mentions"])
return {"retrieval": result, "retrieval_mode": mode, "warnings": result.warnings, "debug": {...}}
```
(traditional KHÔNG dùng `seed_mentions` — đúng thiết kế; build_query vẫn chạy bình thường.)

`graph.py` (topology) **không đổi** — chỉ logic trong node `retrieve` thay đổi.

---

## Phần B — Mode 1: TRADITIONAL sau cải tiến

**Mục tiêu**: dense (semantic) + BM25 (keyword) → RRF → rerank. Tận dụng Qdrant native.

### B1. Hạ tầng BM25 trong Qdrant (offline, 1 lần)

- **Dependency**: thêm `fastembed` vào `apps/agent-service/requirements.txt` (+ root nếu cần).
  Dùng `SparseTextEmbedding("Qdrant/bm25")`. Lý do chọn fastembed client-side thay vì
  server-side inference: **deterministic + dễ unit-test (mock được)**, không phụ thuộc tính
  năng inference của server. (Server 1.18.2 có hỗ trợ server-side nếu sau này muốn bỏ dep.)
- **Collection schema** (`app/core/qdrant.py::ensure_chunks_collection`): giữ nguyên dense
  vector **mặc định (unnamed)**, **thêm** sparse named `"bm25"`:
  ```python
  client.create_collection(
      collection_name=name,
      vectors_config=VectorParams(size=EMBEDDING_DIM, distance=Distance.COSINE),
      sparse_vectors_config={"bm25": SparseVectorParams(modifier=Modifier.IDF)},
  )
  ```
  Dense vẫn unnamed → `search_vector` hiện tại KHÔNG vỡ. `Modifier.IDF` để Qdrant tự tính
  IDF (fastembed Bm25 cố ý bỏ IDF — phải bật modifier này).
- **Reindex sạch (quyết định user 2026-06-30)**: KHÔNG dùng `update_collection`/backfill
  chắp vá. Thay vào đó **drop + recreate collection** với dense+sparse ngay từ đầu rồi
  reindex lại toàn bộ vector. Rẻ vì embedding (local model) + BM25 (local fastembed) đều
  **không tốn API**. Postgres `rag_chunks` + Neo4j graph **giữ nguyên** (source of truth,
  không đổi) → chỉ Qdrant được dựng lại. `point_id = uuid5(chunk_id)` đảm bảo idempotent.
- **`upsert_chunk_vectors`** (`vector_store.py`): tính cả dense + sparse, đính cả hai vào
  point. Dense giữ default unnamed, sparse vào key `"bm25"`:
  ```python
  PointStruct(id=point_id_for(cid), payload=_payload(r), vector={
      "": dense_vec.tolist(),                       # default unnamed dense
      "bm25": SparseVector(indices=idx, values=val),
  })
  ```
  (Hoặc dùng `models.Document`/API tương ứng — verify cú pháp gắn đồng thời unnamed dense +
  named sparse khi implement.) Bọc fastembed Bm25 phù hợp pipeline offline (đang `asyncio.run`).
- **Lệnh reindex**: `reset_stores.py` recreate collection (đã có pattern drop/recreate) →
  `run_graph_index.py --skip-graph` (chỉ dựng lại vector dense+sparse, bỏ qua graph extract
  vì Neo4j + cache `graph_extractions.json` không đổi).

### B2. Truy hồi online (`tools/traditional_rag/retriever.py::retrieve_traditional`)

Đổi từ "dense thuần" → **dense + sparse fuse trong Qdrant** rồi rerank:

1. Embed query (dense) — `embed_texts` sẵn có.
2. Tính sparse query — `bm25.query_embed(query)` (bọc to_thread). Helper mới
   `tools/graph_rag/vector_store.py::search_dense_sparse(query)` hoặc module sparse riêng.
3. **Qdrant Universal Query API** một lần — `client.query_points` với 2 `prefetch`
   (dense default + sparse `using="bm25"`) và `query=FusionQuery(fusion=Fusion.RRF)`:
   ```python
   client.query_points(
       collection_name=col,
       prefetch=[
           Prefetch(query=dense_vec, limit=rag_top_k),                       # dense default
           Prefetch(query=SparseVector(indices, values), using="bm25", limit=bm25_top_k),
       ],
       query=FusionQuery(fusion=Fusion.RRF),
       limit=hybrid_candidate_k, with_payload=True,
   )
   ```
   → Qdrant tự RRF dense+sparse, trả candidate đã gộp (tận dụng Qdrant, không RRF tay).
4. Hydrate full text Postgres — `get_rag_chunks_by_ids` (1 batch, sẵn có).
5. **Rerank** — `core/reranker.rerank(question, chunks)` rồi cắt `rerank_top_k` (đang dùng
   trong hybrid; traditional hiện CHƯA gọi → thêm).
6. Trả `RetrievalResult(mode="traditional", ...)`, `graph_context` rỗng.

> ⚠️ Rerank chỉ chạy thật khi `.env` set `RERANKER_MODEL=AITeamVN/Vietnamese_Reranker`
> (mặc định `reranker_model=""` → no-op). Cần ghi vào `.env`.

### B3. Pre-filter metadata — **KHÔNG LÀM (chốt user 2026-07-01)**

**Tuyệt đối không làm** pre-filter metadata ở giai đoạn này. Không mở rộng `BuildQueryOutput`,
không thêm `Filter`/`should`/score-boost trên payload Qdrant, không đụng `query_actors`/
`query_locations`. Metadata để **rerank xử lý gián tiếp**. Có thể xem lại sau nếu có thời
gian — không thì thôi.

<details><summary>Ý tưởng cũ (lưu lại để tham khảo về sau, KHÔNG triển khai)</summary>

Dùng actor/location LLM trích được (chuẩn hóa qua `alias_map.json`) làm filter MỀM trên
payload Qdrant (`actors`/`locations`). Soft, không hard-AND: `should` OR-gate hoặc score-boost
(FormulaQuery). Bỏ `times` khỏi filter. Cần mở rộng `BuildQueryOutput` trả riêng
`query_actors`/`query_locations`.
</details>

---

## Phần C — Mode 2: GRAPH sau cải tiến (path-finding)

**File chính**: `app/tools/graph_rag/graph_store.py::search_graph` + Cypher mới.

### C1. Giữ nguyên (đang tốt)
- Ground seed (`match_seed_entities`): LLM `seed_mentions` → fallback `token_match`; hub
  guard; cap `graph_max_seed_entities`.
- Mỗi seed expand **1-hop** (`_EXPAND_SEED`) → entity + relation 1-hop làm `graph_context`,
  score chunk (`_SEED_HIT=2.0`, `_EDGE_HIT=1.0`, hub weight `0.25`, cap mỗi seed).

### C2. THÊM: path-finding giữa các seed (kích hoạt khi ≥2 seed)
Khi có ≥2 seed đã ground, tìm **đường nối** từng cặp để trả lời câu hỏi quan hệ:
```cypher
MATCH path = shortestPath(
  (a:Entity {norm_name:$a})-[:REL*1..{MAXHOP}]-(b:Entity {norm_name:$b})
)
RETURN [n IN nodes(path) | {name:n.name, norm:n.norm_name,
                            descriptions:n.descriptions, chunks:n.source_chunk_ids}] AS nodes,
       [r IN relationships(path) | {keyword:r.keyword, descriptions:r.descriptions,
                                    chunks:r.source_chunk_ids,
                                    src:startNode(r).norm_name, tgt:endNode(r).norm_name}] AS rels
```
- `{MAXHOP}` = `graph_max_path_hops` (mặc định 3) — **nội suy int đã validate vào chuỗi
  Cypher** (Neo4j không parametrize được cận var-length; cùng lý do file này không
  parametrize label/rel-type). MAXHOP là hằng config, KHÔNG phải input user → an toàn.
- Số cặp = C(n,2), với cap 5 seed → tối đa 10 cặp. `shortestPath` = 1 đường/cặp → **bị
  chặn, không bùng nổ**.
- Node/relation trên path → thêm vào `graph_context` (tái dùng `GraphContextItem` +
  `dedup_key()` để không trùng với phần 1-hop). Chunk trên path → score (trọng số mới
  `_PATH_HIT`, ví dụ 1.5) + thêm candidate.
- Không có đường nối → bỏ qua cặp đó (honest, không bịa).

### C3. Khi không ground được seed — trả lời honest, gợi ý đổi mode (chốt user 2026-07-01)
Hiện không match seed → `search_graph` trả `([],[])`. **KHÔNG auto-fallback** sang
`retrieve_traditional`; **KHÔNG** thêm config `graph_empty_fallback`. Thay vào đó node
`retrieve` (mode=`graph`) đi tới honest_answer với **thông điệp rõ ràng cho user**: đại ý
*"Không tìm thấy nội dung phù hợp ở chế độ Graph. Bạn hãy thử lại với mode khác
(Traditional / Hybrid)."* Không tự đổi mode thay user.

- Cần đánh dấu lý do rỗng (vd field state/`warnings` `"graph_no_seed"`) để synthesize/
  honest_answer chọn đúng message gợi ý đổi mode (thay vì message "thiếu dữ liệu" chung).
- Giữ đúng tinh thần **honest behavior + user chọn tay** (không Query Routing ngầm).

### C4. KHÔNG rerank cho standalone graph (chốt user 2026-07-01)
`retrieve_graph` **giữ nguyên — không thêm `rerank()`**. Thứ tự kết quả theo graph score
(seed / edge / path hit). Lý do: graph score và query-similarity đo hai thứ khác nhau; user
chốt không rerank ở standalone graph. (Hybrid vẫn rerank như D2 — đó là lớp composition
riêng, không mâu thuẫn.)

---

## Phần D — Mode 3: HYBRID sau cải tiến

**Nguyên tắc**: hybrid là lớp COMPOSITION, gọi **primitive** (`search_vector`,
`search_graph`, + mới `search_bm25`) — KHÔNG gọi facade nặng (tránh rerank/hydrate 2 lần).
Cải tiến đặt ở primitive → hybrid tự kế thừa.

**File**: `app/tools/hybrid/retriever.py::retrieve_hybrid` + `schemas/retrieval.py`.

### D1. Nâng RRF từ 2 nguồn → **3 nguồn** (dense + sparse BM25 + graph)
- `schemas/retrieval.py`: `CandidateSource = Literal["vector","graph"]` → thêm `"sparse"`.
  `_SOURCE_ORDER` trong hybrid thêm `"sparse"`. (Tùy chọn: `RetrievedChunk.sparse_score`.)
- Thêm `search_bm25(query, top_k)` (primitive sparse-only, trả `RetrievalCandidate[source="sparse"]`).
- `retrieve_hybrid`: thêm `_bm25_candidates()` vào `asyncio.gather` (song song cùng vector +
  graph). RRF loop chỉ cần đổi `[*vec_cands, *graph_cands]` → `[*vec_cands, *bm25_cands, *graph_cands]`
  (loop đã generalize sẵn). Nguồn nào chết → warning + degrade (đã có pattern).

### D2. Tự kế thừa — KHÔNG cần code thêm
- **Path-finding**: hybrid gọi `search_graph` → path-finding nằm trong đó → `graph_context`
  giàu hơn ride along tự động. ✓
- **Rerank**: hybrid ĐÃ có (`rerank` + cắt `rerank_top_k`). ✓
- **Rule B** (union `source_chunk_ids` của graph_context để giữ citation): giữ nguyên. ✓

> Pre-filter KHÔNG làm (chốt user — xem B3) nên hybrid cũng không truyền `query_filter`.
> Lưu ý hành vi graph-rỗng ở C3 (gợi ý đổi mode) là cho **standalone graph**; trong hybrid
> graph chỉ là 1 nguồn của RRF nên graph rỗng chỉ degrade + warning, KHÔNG kích message
> "đổi mode".

---

## Phần E — Config knobs thêm (`app/core/config.py`)

```python
bm25_model: str = "Qdrant/bm25"        # fastembed sparse encoder
bm25_top_k: int = 20                    # sparse candidates
sparse_vector_name: str = "bm25"        # tên named sparse trong Qdrant
graph_max_path_hops: int = 3            # cận shortestPath
graph_path_hit_weight: float = 1.5      # trọng số chunk trên path
```
> KHÔNG thêm `graph_empty_fallback` (chốt user — graph rỗng trả lời gợi ý đổi mode, xem C3).
`.env`: set `RERANKER_MODEL=AITeamVN/Vietnamese_Reranker` để rerank chạy thật.

---

## Phần F — Kỹ thuật RAG khác: CHỈ làm Document Reordering (chốt user 2026-07-01)

> Phần này **độc lập** với 3 mode trên. ✓ = đã có. Chốt: **CHỈ triển khai Document
> Reordering**; mọi kỹ thuật còn lại trong bảng **KHÔNG làm**.

| Kỹ thuật | Hoạt động (1 dòng) | Quyết định |
|---|---|---|
| Dense / Sparse / Hybrid / RRF / Reranking | (3 mode ở trên) | ✓ Đang làm |
| Pre-filtering | Lọc metadata trước search | **KHÔNG** (chốt — xem B3) |
| MMR (đa dạng) | Chọn chunk vừa liên quan vừa ít trùng nhau | **KHÔNG** (chốt user) |
| **Document Reordering** | Xếp chunk tốt ra đầu/cuối prompt (chống "lost in the middle") | **LÀM** (chốt user) — rất rẻ, cải thiện synth |
| Context Deduplication | Bỏ chunk gần trùng nội dung | **KHÔNG** (chốt user) |
| Context Compression | Cắt/nén chunk cho gọn context | **KHÔNG** (chốt user) |
| Token Budget Mgmt | Giới hạn tổng token đưa LLM | **KHÔNG** (chốt user) |
| Citation Generation / Grounding / Abstention | Trích nguồn + từ chối khi thiếu data | ✓ Đã có (`validate_citations`, `honest_answer`) |
| Self-correction | Synth lỗi → thử lại | ✓ Đã có (`synthesize` retry) |
| Streaming / Safety filter | Stream token + guardrails | ✓ Đã có (SSE + `guardrails`) |
| Query Routing | LLM tự chọn mode/nguồn | **KHÔNG** — user yêu cầu CHỌN TAY, xung đột |
| Instruction Tuning | Fine-tune model | **KHÔNG** — ngoài scope đồ án |
| Parent-child Retrieval | Tìm chunk nhỏ → mở rộng parent | **KHÔNG** — phải re-chunk |
| Multi-index / Conflict Resolution / Multi-step / CoT / PII | Các kỹ thuật nâng cao/không hợp domain | **KHÔNG** — overkill hoặc không hợp corpus lịch sử |

**Document Reordering** (mục duy nhất triển khai): đặt ở bước **sau retrieve, trước
synthesize**, áp chung cho cả 3 mode. Sau khi đã có danh sách chunk xếp theo điểm (rerank /
graph score / RRF), sắp lại sao cho chunk điểm cao nằm ở **đầu và cuối** context, chunk điểm
thấp dồn vào giữa (chống "lost in the middle"). Thuần sắp xếp, không gọi LLM, không bỏ chunk.

---

## Phần G — Kiểm thử (verification)

**Unit test** (mock backend, theo pattern `tests/` sẵn có):
- `test_traditional_retriever.py`: mock dense+sparse Query API fusion, verify rerank được gọi + cắt `rerank_top_k`.
- `test_graph_search.py`: thêm case ≥2 seed → path-finding trả node/relation trên path; case không có đường; cap số cặp.
- `test_hybrid_retriever.py`: 3-way RRF (dense+sparse+graph), degrade khi 1 nguồn chết, `graph_context` passthrough.
- Test mới: dispatch mode trong `nodes.retrieve()` (3 mode gọi đúng retriever).
- Backend: `/ask` nhận `mode`, proxy đúng.

**Tích hợp tay**:
1. `reset_stores.py` (recreate collection dense+sparse) → `run_graph_index.py --skip-graph` → verify points có cả dense lẫn `bm25` sparse vector (`client.scroll(..., with_vectors=True)`).
2. Set `RERANKER_MODEL` trong `.env`.
3. Chạy agent (`uvicorn app.main:app --port 9000`), gọi `/ask` với `mode` lần lượt
   `traditional` / `graph` / `hybrid`, so sánh chất lượng + `retrieval_mode` trả về.
4. Câu test graph path-finding: *"Quan hệ giữa Phan Bội Châu và Phan Châu Trinh?"* → kiểm
   `graph_context` có relation nối hai entity.

**Lint/type/test**:
```powershell
.\venv\Scripts\python.exe -m ruff check apps/agent-service/app apps/backend/app
.\venv\Scripts\python.exe -m mypy apps/agent-service/app
.\venv\Scripts\python.exe -m pytest apps/agent-service/tests
.\venv\Scripts\python.exe -m pytest apps/backend/tests
```

---

## Thứ tự triển khai đề xuất
1. **Plumbing chọn mode** (Phần A) — nhỏ, mở khóa cho user test 3 mode ngay (traditional/graph hiện có sẵn facade). Kèm honest "gợi ý đổi mode" khi graph rỗng (Phần C3).
2. **Graph path-finding** (Phần C2) — giá trị cao nhất, điểm contribution. KHÔNG rerank standalone graph (C4).
3. **Traditional BM25 + rerank** (Phần B, KHÔNG kèm B3) — gồm reindex Qdrant sạch (dense+sparse).
4. **Hybrid 3-way** (Phần D) — sau khi có `search_bm25`.
5. **Document Reordering** (Phần F) — bồi đắp cuối, áp chung 3 mode.

> ~~Pre-filter (B3)~~ và ~~MMR / Dedup / Compression~~: **KHÔNG làm** (chốt user 2026-07-01).
