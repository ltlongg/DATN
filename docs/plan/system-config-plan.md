# Plan System Config — Cấu hình hệ thống (retrieval + synthesize, áp dụng LIVE)

## Context

Tách riêng khỏi `docs/plan/backend-additions-plan.md` (2026-07-01) vì đây là phần **nặng và
rủi ro nhất** trong Module 4 admin nâng cao — đụng nhiều file orchestrator đang chạy ổn định
(`state.py`, `runner.py`, `nodes.py::retrieve()`/`synthesize()`/`honest_answer()`/
`direct_response()`, 3 module retriever traditional/graph/hybrid, `graph_store.py`,
`vector_store.py`, `synthesis.py`) cả phía backend lẫn agent-service lẫn frontend.

**Thứ tự làm**: **SAU KHI** hoàn thiện xong 4 phần trong `backend-additions-plan.md` (Debug
streaming, KB Inspector, Hội thoại & chất lượng, Người dùng & quota). Frontend tab Cấu hình
hệ thống trong lúc đó hiện **"Sắp cập nhật"** (xem `frontend-plan.md` Pha C — đã đổi thành
stub, trỏ về plan này). Có plan sẵn ở đây để khi tới lượt làm thì cứ theo mà code, không phải
thiết kế lại từ đầu.

> **Thuật ngữ**: role không-phải-admin gọi là **"user"** ở mô tả; **giá trị literal trong
> code vẫn là `teacher`**.

---

## Quyết định đã chốt (7 vòng, vòng 3+4 sửa lại vòng 1, vòng 5 bỏ prompt override, vòng 6+7
đối chiếu lại code thật — 2026-07-06)

1. ~~KHÔNG có toggle bật/tắt~~ → **SỬA LẠI (vòng 3)**: 3 mode (traditional/graph/hybrid)
   LUÔN CÙNG TỒN TẠI trong hệ thống (không mode nào bị xoá/gỡ code) — là **1 field lựa
   chọn (enum)**, KHÔNG PHẢI 2 công tắc độc lập bật/tắt riêng từng cái (thiết kế 2-boolean
   trước đó là hiểu sai ý, đã bỏ).
1b. **SỬA LẠI (vòng 4)**: mode KHÔNG chỉ admin chọn — **user (mọi role) cũng chọn được cho
   TỪNG câu hỏi của mình**, ngay trong khung chat, không cần vào trang admin. Thiết kế 2
   lớp: **admin đặt mode MẶC ĐỊNH** (`system_config.retrieval_backend`, áp cho toàn hệ
   thống khi user không chỉ định) + **user override PER-CÂU HỎI** (field mới trên
   `AskRequest`, giống cơ chế `debug` hiện có — chỉ áp cho đúng câu hỏi đó, không đổi mặc
   định chung). Xem thiết kế field mới ở §Backend/Agent-service bên dưới.
1c. **SỬA LẠI (vòng 6) — quan trọng, đối chiếu code thật lúc này (2026-07-06)**: phần "user
   chọn mode per-câu-hỏi" ở 1b **ĐÃ CÓ SẴN, không phải làm mới**. Field `mode` đã tồn tại và
   wiring END-TO-END từ trước: FE `Composer.tsx` (dropdown "Cách truy hồi", 3 lựa chọn) →
   backend `schemas/chat.py::AskRequest.mode` → `services/agent_client.py::AgentAskRequest.mode`
   → agent-service `schemas/ask.py::AskRequest.mode` → `AgentState["requested_mode"]` →
   `nodes.py::retrieve()` dispatch. Debug cũng đã có sẵn `debug.retrieve.mode` = giá trị mode
   đã resolve ([nodes.py:198-204](apps/agent-service/app/orchestrator/nodes.py#L198-204)) —
   KHÔNG cần thêm field debug mới. Điểm THẬT SỰ còn thiếu chỉ là: field `mode` hiện
   **LUÔN BẮT BUỘC, default cứng `"hybrid"`** ở cả 3 tầng (không phải `| None`), nên chưa có
   khái niệm "để trống = dùng mặc định admin đặt". Việc cần làm thu hẹp lại còn: (a) đổi type
   3 field trên thành `Literal[...] | None = None`, (b) FE thêm 1 lựa chọn "Mặc định hệ
   thống" gửi `undefined` thay vì chọn cứng 1 trong 3, (c) resolve fallback trong
   `runner.py` — xem §Backend/Agent-service đã viết lại bên dưới. KHÔNG tạo field mới tên
   `retrieval_backend_override` như dự định ban đầu — dùng lại đúng field `mode`/
   `requested_mode` đã có để khỏi trùng lặp khái niệm.
2. KHÔNG quản lý model (bỏ hẳn `llm_model_override`).
3. Quản lý HẾT các tham số tinh chỉnh khác đang nằm trong `app/core/config.py::Settings` —
   cả phía **retrieval** (rag_top_k, graph_top_k, hybrid_candidate_k, hybrid_rrf_k,
   rerank_top_k, graph_max_seed_entities, graph_max_chunks_per_seed,
   graph_hub_source_count_threshold, graph_max_context_items, **+ 3 field mới phát hiện lúc
   đối chiếu code — vòng 6**: bm25_top_k, graph_max_path_hops, graph_path_hit_weight) lẫn
   phía **synthesize** (temperature, ~~prompt override~~, ~~synthesize_max_attempts~~,
   stream_batch_chars). Riêng 12 field tinh chỉnh retrieval + 2 field synthesize KHÔNG có
   bản override per-câu-hỏi — chỉ `mode`/`retrieval_backend` mới cần override per-câu-hỏi
   (vì đây là lựa chọn mà USER — không chỉ admin — quan tâm trực tiếp: "muốn hỏi kiểu tra
   cứu văn bản hay theo quan hệ nhân vật/sự kiện").
3b. **SỬA LẠI (vòng 5)**: bỏ hẳn `synthesize_prompt_override` khỏi scope plan này — đã có hệ
   thống **quản lý prompt riêng, đầy đủ hơn** (`docs/plan/admin-restructure-plan.md` Item 2,
   **đã code xong và đang chạy thật**): `app/tools/prompts/prompt_store.py::get_active_prompt`
   + 2 bảng `managed_prompts`/`prompt_versions` + CRUD/version/promote qua
   `/api/admin/prompts` (FE `features/prompts/`). Hệ thống đó có **version history + rollback
   thật** (khác field textarea ghi-đè-toàn-văn dự định ở đây, KHÔNG có version history) và đã
   wiring sẵn cho đúng 3 prompt online (`build_query`, `synthesize`, `guardrails_input`). Thêm
   `synthesize_prompt_override` vào `system_config` sẽ tạo **2 cơ chế song song ghi đè cùng 1
   system prompt** (chồng chéo, khó biết cái nào thắng) — nên KHÔNG làm nữa.
3c. **MỚI (vòng 7) — cũng đối chiếu code thật**: bỏ luôn `synthesize_max_attempts` khỏi scope
   (khác 3b, đây KHÔNG phải vì đã có chỗ quản lý tốt hơn, mà vì **cơ chế nó phục vụ hiện
   KHÔNG TỒN TẠI**). [graph.py:11](apps/agent-service/app/orchestrator/graph.py#L11) ghi rõ
   "TẠM BỎ validate_citations/after_validate (trust-boundary + retry loop) để đơn giản hóa
   flow lúc dev" — graph hiện đi thẳng `synthesize → build_visualization → END`, KHÔNG có
   nhánh nào đọc lại `synthesize_max_attempts` để quyết định retry. Đưa field này vào
   `system_config` lúc này sẽ là **config admin chỉnh được nhưng KHÔNG có tác dụng gì** — vi
   phạm đúng nguyên tắc plan tự đặt ra ("KHÔNG phải trình xem read-only, giá trị phải áp
   dụng thật"). Khi nào `after_validate`/retry loop được làm lại (việc khác, ngoài phạm vi
   plan này) thì mới thêm field này trở lại.

**Nguyên tắc riêng cho nhóm này**: đây KHÔNG phải trình xem read-only kiểu Module 5. Khi
admin bấm lưu, giá trị phải **áp dụng thật vào agent-service** — không cần restart. Độ trễ áp
dụng tối đa = TTL cache (xem dưới, ~60s, đồng bộ pattern `prompt_store` đã có trong repo) —
KHÔNG phải tức thời tuyệt đối ở câu hỏi ngay sau đó, nhưng đủ nhanh để demo/dùng thật.

---

## Backend + agent-service — wiring THẬT

**Vì sao đọc thẳng Postgres thay vì gọi HTTP sang agent-service**: Postgres đã là "source of
truth" DÙNG CHUNG giữa 2 service (CLAUDE.md §Storage roles — agent-service đã tự đọc/ghi
`rag_chunks`/`timeline_events`/`gazetteer` trực tiếp bằng `psycopg`, không qua backend).
`system_config` đi theo đúng pattern đó: **backend sở hữu DDL + API ghi** (vì chỉ backend có
endpoint admin), **agent-service tự đọc thẳng** bảng này — không phải gọi API backend, không
có bước "backend đẩy config sang agent" nào cả. Điều này KHÔNG vi phạm nguyên tắc "backend
không phải là agent" (nguyên tắc đó nói về logic LLM/retrieval, không nói về ai được đọc bảng
nào trong DB dùng chung).

**2 lớp giảm I/O, mirror đúng pattern `prompt_store.get_active_prompt` đã có trong repo**:

1. **In-process cache TTL bên trong `get_runtime_config()`** — module-level cache dạng
   `(hết_hạn_lúc, RuntimeConfig)`, TTL ~60s (đồng bộ `prompt_store._CACHE_TTL_SECONDS`) — còn
   hạn thì trả thẳng từ RAM, hết hạn mới query lại 1 dòng Postgres và reset đồng hồ. Chọn cache
   in-process thay vì Redis vì 1 dòng Postgres vốn đã rẻ (~vài ms, không đáng so với thời gian
   LLM call của cả request) — thêm Redis (write-through, xử lý cache miss/down) là phức tạp
   hoá không cần thiết cho lợi ích biên rất nhỏ; in-process TTL vừa đủ để giảm số round-trip
   khi traffic tăng, lại mirror đúng pattern `prompt_store` đã kiểm chứng trong repo. Đánh đổi
   chấp nhận được (giống prompt đang chạy thật): nếu agent-service chạy nhiều worker process,
   mỗi worker giữ cache riêng, độ trễ áp dụng lệch tối đa TTL giây giữa các worker — không cần
   cơ chế bust cache chéo process vì backend và agent-service là 2 tiến trình khác nhau (không
   gọi hàm nội bộ của nhau được).
2. **Trong 1 request, chỉ gọi `get_runtime_config()` đúng 1 LẦN, lưu vào `state`**: nếu để
   mỗi node (`retrieve`, `synthesize`, `honest_answer`, `direct_response`) tự gọi riêng thì
   MỘT câu hỏi tốn tới 4 lượt gọi. Giải pháp: gọi đúng 1 lần **trước khi vào graph**
   (`run_ask`/`run_ask_stream`, ngay đầu — cũng là nơi duy nhất cần resolve `mode` per-câu-hỏi,
   xem khối ngay dưới), nhét vào `AgentState["runtime_config"]` (dict), mọi node sau chỉ ĐỌC
   từ `state` — không gọi lại hàm, không I/O gì thêm. (Bản trước của plan còn nhắc
   `after_validate` ở đây — node đó hiện KHÔNG tồn tại trong graph, xem quyết định 3c.)

**`mode` per-câu-hỏi (user, mọi role) — field ĐÃ CÓ SẴN, chỉ cần nới lỏng + resolve mặc định**:
Khác các field còn lại (chỉ admin chỉnh qua `/api/admin/config`), mode retrieval đã có
đường đi per-request từ trước — user chọn NGAY TRONG khung chat cho từng câu hỏi qua field
`mode` (KHÔNG phải field mới tên `retrieval_backend`, xem quyết định 1c). Việc cần làm chỉ
là biến field bắt buộc hiện tại thành "tùy chọn, để trống = theo mặc định admin đặt":

1. **agent-service — `app/schemas/ask.py::AskRequest.mode`**: đổi
   `mode: RetrievalMode = "hybrid"` → `mode: RetrievalMode | None = None` (`None` = không
   chỉ định, dùng mặc định từ `system_config`; giá trị cụ thể vẫn override như cũ — hành vi
   KHÔNG đổi cho request nào đã luôn truyền `mode` tường minh).
2. **backend — `app/schemas/chat.py::AskRequest.mode`** (frontend → backend): đổi tương tự
   `Literal["traditional","graph","hybrid"] = "hybrid"` → `... | None = None`; backend KHÔNG
   gác role ở field này (đã đúng từ trước — field này mọi role dùng được, không riêng admin).
   `apps/backend/app/services/agent_client.py::AgentAskRequest.mode` đổi cùng kiểu, forward
   nguyên giá trị (kể cả `None`) sang agent-service.
3. **agent-service — `app/orchestrator/state.py::AgentState["requested_mode"]`**: KHÔNG thêm
   field mới — đây đã là field tồn tại, dùng để dispatch trong `retrieve()`. Chỉ cần đảm bảo
   giá trị nhét vào nó lúc `initial_state` đã là mode ĐÃ RESOLVE (không còn `None`) — xem
   bước 4.
4. **agent-service — `app/orchestrator/runner.py`**: đây là nơi DUY NHẤT cần đọc
   `system_config` để resolve fallback (không đụng `nodes.py::retrieve()` — hàm đó tiếp tục
   dispatch theo `state["requested_mode"]` y như hiện tại, không cần biết gì về override):
   ```python
   cfg = await asyncio.to_thread(get_runtime_config)
   state = initial_state(request, resolved_mode=request.mode or cfg.retrieval_backend)
   state["runtime_config"] = cfg.model_dump()
   ```
   `initial_state()` ([runner.py:20](apps/agent-service/app/orchestrator/runner.py#L20))
   thêm tham số `resolved_mode: RetrievalMode`, set `"requested_mode": resolved_mode` thay vì
   `"requested_mode": request.mode` như hiện tại.
5. **Debug — KHÔNG cần thêm gì**: [nodes.py:198-204](apps/agent-service/app/orchestrator/nodes.py#L198-204)
   đã ghi `debug.retrieve.mode` = giá trị `mode` đã dùng để dispatch (tức giá trị ĐÃ RESOLVE)
   — admin đã thấy đúng mode nào thật sự chạy, kể cả khi user tự chọn khác mặc định hệ thống.
6. Test: agent-service — test resolve ở `runner.py` (hoặc hàm helper tách riêng cho dễ test):
   `request.mode` có giá trị → dùng đúng giá trị đó (bỏ qua `cfg.retrieval_backend`);
   `request.mode is None` → rơi về `cfg.retrieval_backend`; backend — field `mode` chấp nhận
   `None`/thiếu field (không bắt buộc nữa), giá trị sai enum → 422 từ Pydantic.

**Bảng `system_config`** (DDL ở `app/core/db.py`, backend sở hữu — singleton 1 dòng; default
= **y hệt** giá trị hardcode hiện tại trong `Settings` → tạo bảng xong KHÔNG đổi hành vi gì
cho tới khi admin thật sự chỉnh):
```sql
CREATE TABLE IF NOT EXISTS system_config (
    id                                SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    -- chọn 1 trong 3 mode LUÔN tồn tại sẵn — KHÔNG phải 2 công tắc độc lập
    retrieval_backend                TEXT NOT NULL DEFAULT 'hybrid'
                                         CHECK (retrieval_backend IN ('traditional','graph','hybrid')),
    -- retrieval (khớp default hiện tại trong app/core/config.py::Settings)
    rag_top_k                        INTEGER NOT NULL DEFAULT 20  CHECK (rag_top_k > 0),
    graph_top_k                      INTEGER NOT NULL DEFAULT 20  CHECK (graph_top_k > 0),
    hybrid_candidate_k               INTEGER NOT NULL DEFAULT 30  CHECK (hybrid_candidate_k > 0),
    hybrid_rrf_k                     INTEGER NOT NULL DEFAULT 60  CHECK (hybrid_rrf_k > 0),
    rerank_top_k                     INTEGER NOT NULL DEFAULT 8   CHECK (rerank_top_k > 0),
    graph_max_seed_entities           INTEGER NOT NULL DEFAULT 5   CHECK (graph_max_seed_entities > 0),
    graph_max_chunks_per_seed        INTEGER NOT NULL DEFAULT 20  CHECK (graph_max_chunks_per_seed > 0),
    graph_hub_source_count_threshold INTEGER NOT NULL DEFAULT 80  CHECK (graph_hub_source_count_threshold > 0),
    graph_max_context_items          INTEGER NOT NULL DEFAULT 12  CHECK (graph_max_context_items > 0),
    -- 3 field mới phát hiện lúc đối chiếu code thật (vòng 6) — có trong Settings nhưng bản
    -- đầu của plan này bỏ sót:
    bm25_top_k                       INTEGER NOT NULL DEFAULT 20  CHECK (bm25_top_k > 0),
    graph_max_path_hops              INTEGER NOT NULL DEFAULT 3   CHECK (graph_max_path_hops > 0),
    graph_path_hit_weight            REAL NOT NULL DEFAULT 1.5    CHECK (graph_path_hit_weight >= 0),
    -- synthesize
    llm_temperature                  REAL NOT NULL DEFAULT 0.0
                                         CHECK (llm_temperature >= 0 AND llm_temperature <= 2),
    -- KHÔNG có synthesize_prompt_override: prompt quản lý riêng qua managed_prompts/
    -- prompt_versions (docs/plan/admin-restructure-plan.md Item 2, đã code) — tránh 2 cơ chế
    -- ghi đè cùng 1 system prompt chồng chéo nhau.
    -- KHÔNG có synthesize_max_attempts: cơ chế after_validate/retry loop nó phục vụ đã bị gỡ
    -- khỏi graph.py (xem quyết định 3c) — chưa có chỗ để field này có tác dụng.
    stream_batch_chars               INTEGER NOT NULL DEFAULT 160 CHECK (stream_batch_chars > 0),
    updated_at                       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (rerank_top_k <= hybrid_candidate_k)  -- rerank cắt TỪ pool đã fuse, không thể lớn hơn pool
);
INSERT INTO system_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
```

**Field nào wiring thật, field nào KHÔNG làm (nói rõ để khỏi nửa vời)**:
| Field | Áp dụng vào đâu | Ghi chú |
|-------|------------------|---------|
| `retrieval_backend` (`traditional`\|`graph`\|`hybrid`, mặc định hệ thống) | Resolve trong `runner.py` thành `requested_mode`, dùng bởi `nodes.py::retrieve()` **dispatch sang 1-trong-3 hàm khác nhau** (KHÔNG phải cờ bật/tắt trong 1 hàm — xem ghi chú) | Thực tế `retrieve()` ([nodes.py:178-193](apps/agent-service/app/orchestrator/nodes.py#L178-193)) gọi `retrieve_traditional`/`retrieve_graph`/`retrieve_hybrid` — 3 module hoàn toàn khác nhau, KHÔNG phải `retrieve_hybrid(enable_vector=, enable_graph=)` như bản trước của plan giả định. `mode` per-câu-hỏi đã có sẵn field (`AskRequest.mode`), phần mới chỉ là fallback về mặc định hệ thống (xem quyết định 1c) |
| `rag_top_k` | `traditional` → `retrieve_traditional(question, top_k=)` (seam có sẵn) → `search_dense_sparse`; `hybrid` → `retrieve_hybrid` cần thêm kwarg `rag_top_k` forward xuống `search_vector`/`search_bm25` (seam `top_k` đã có ở cả 2 hàm) | |
| `graph_top_k` | `graph` → `retrieve_graph(query, ..., top_k=)` — **retrieve_graph CHƯA có seam này**, cần thêm kwarg mới rồi forward vào `search_graph(..., top_k=)` (seam của `search_graph` đã có); `hybrid` → tương tự qua `_graph_candidates` | |
| `hybrid_candidate_k` / `hybrid_rrf_k` / `rerank_top_k` | `rerank_top_k` áp cho CẢ 3 mode (traditional/graph/hybrid đều rerank + cắt bằng field này, hiện đọc `get_settings().rerank_top_k` trực tiếp ở 3 chỗ khác nhau); `hybrid_candidate_k`/`hybrid_rrf_k` chỉ áp cho `retrieve_hybrid` (đọc trực tiếp `settings.X` hiện tại — cần thêm kwarg optional, giữ tương thích ngược) | |
| `bm25_top_k` (field mới — vòng 6) | `retrieve_traditional`/`retrieve_hybrid` — `search_dense_sparse` đọc `settings.bm25_top_k` cho nhánh sparse của Prefetch ([vector_store.py:172](apps/agent-service/app/tools/graph_rag/vector_store.py#L172), CHƯA có seam); `search_bm25` đã có seam `top_k` riêng dùng cho hybrid | |
| `graph_max_seed_entities` / `graph_max_chunks_per_seed` / `graph_hub_source_count_threshold` / `graph_max_context_items` | đọc trực tiếp `settings.X` bên trong `search_graph` ([graph_store.py:253/261/283/391](apps/agent-service/app/tools/graph_rag/graph_store.py#L253)) — cần thêm 4 kwarg optional mới, cùng pattern `None → fallback settings.X` | |
| `graph_max_path_hops` / `graph_path_hit_weight` (2 field mới — vòng 6) | đọc trực tiếp `settings.X` trong `search_graph` ([graph_store.py:328-329](apps/agent-service/app/tools/graph_rag/graph_store.py#L328-329)) cho path-finding giữa các seed — cần thêm 2 kwarg optional | |
| `llm_temperature` | `stream_synthesis(..., temperature=)` — LLM call synthesize | build_query GIỮ NGUYÊN `temperature=0.0` cứng (không cho chỉnh) — cần deterministic cho routing/rewrite, đổi ở đây dễ phá route/entity extraction |
| ~~`synthesize_prompt_override`~~ | KHÔNG đưa vào config | Chốt vòng 5: đã có hệ thống quản lý prompt riêng với version history + rollback thật (`admin-restructure-plan.md` Item 2, `prompt_store.py::get_active_prompt`, đã wiring cho `synthesize`) — thêm field này vào `system_config` sẽ tạo 2 cơ chế ghi đè chồng chéo |
| ~~`synthesize_max_attempts`~~ | KHÔNG đưa vào config | Chốt vòng 7: `after_validate()`/retry loop nó phục vụ đã bị gỡ khỏi `graph.py` ("TẠM BỎ ... để đơn giản hóa flow lúc dev") — hiện KHÔNG có node nào đọc field này, thêm vào config sẽ là field không tác dụng |
| `stream_batch_chars` | `synthesize()`, `honest_answer()`, `direct_response()` — cùng 1 tham số batching hiện dùng ở cả 3 chỗ | |
| ~~model (`llm_model`/`orchestrator_llm_model`/...)~~ | KHÔNG đưa vào config | Chốt vòng 2: không quản lý model |
| ~~`embedding_model`/`chunk_size`/`qdrant_collection`~~ | KHÔNG đưa vào config | Đây là tham số INDEX-TIME — đổi mà không re-index sẽ desync với dữ liệu đã index, ngoài phạm vi "áp dụng live" |
| ~~`reranker_model`/`bm25_model`/`sparse_vector_name`/`reranker_max_length`~~ (phát hiện vòng 6) | KHÔNG đưa vào config | Cùng nhóm với model/index-time param ở trên: chọn model rerank/sparse + tên named vector Qdrant — đổi mà không re-index/re-config Qdrant sẽ vỡ, ngoài phạm vi "tinh chỉnh số" của plan này |
| ~~`ask_max_question_chars`/`ask_max_history_messages`~~ | KHÔNG đưa vào config | Bị "đóng băng" ở tầng Pydantic `Field(max_length=...)` lúc định nghĩa class (cả backend lẫn agent-service) — muốn sửa live cần đổi sang custom validator đọc config mỗi lần, việc khác/lớn hơn, để đợt sau |
| ~~ngưỡng hỏi lại/từ chối (số)~~ | KHÔNG đưa vào config | `confidence`/`route` là categorical do LLM structured-output quyết định, không phải so sánh ngưỡng số |

- **backend — `app/models/config.py`** (mới): `SystemConfig` pydantic (15 field trên — 12
  retrieval + 2 synthesize + `retrieval_backend`, gồm
  `retrieval_backend: Literal["traditional","graph","hybrid"]`) + `get_config()` +
  `update_config(fields: dict)`. Validate range/enum ở tầng Pydantic schema TRƯỚC khi update
  (khớp các CHECK ở DB); DB CHECK là lưới an toàn cuối — map `psycopg.errors.CheckViolation`
  → `AppError(422, "validation_error", ...)` nếu lọt qua.
- **backend — `app/schemas/config.py`** + **`app/api/config.py`** (prefix
  `/api/admin/config`, `require_admin`): `GET /api/admin/config`, `PUT /api/admin/config`
  (`exclude_unset` cho phép sửa từng phần). Đăng ký `main.py`.
- **agent-service — `app/core/runtime_config.py`** (mới): `RuntimeConfig` pydantic (default =
  y hệt `Settings` hiện tại) + `get_runtime_config(database_url=None) -> RuntimeConfig` —
  mirror 1:1 `prompt_store.py::get_active_prompt`: module-level cache
  `_cache: tuple[float, RuntimeConfig] | None`, `_CACHE_TTL_SECONDS = 60.0` (đúng số với
  `prompt_store`); còn hạn → trả thẳng cache, hết hạn → `psycopg.connect` trực tiếp (cùng
  pattern `_database_url()` như `chunk_store.py`) đọc lại, ghi cache mới rồi trả. Bắt
  `psycopg.errors.UndefinedTable` + `psycopg.OperationalError` → resolve về `RuntimeConfig()`
  mặc định **và vẫn cache giá trị mặc định đó đủ TTL** (y hệt cách `prompt_store` cache
  fallback khi thiếu version production — đơn giản, nhất quán, chấp nhận được vì fallback là
  giá trị an toàn) — agent-service KHÔNG sập nếu backend chưa `init_db.py` hoặc mất kết nối
  tạm thời. Thêm `clear_cache()` (mirror `prompt_store.clear_cache`) cho test bust cache.
- **agent-service — `app/orchestrator/state.py::AgentState`**: thêm field
  `runtime_config: dict[str, object]` (overwrite thường, KHÔNG cần reducer — ghi 1 lần đầu
  request, chỉ đọc sau đó).
- **agent-service — `app/orchestrator/runner.py`**: `run_ask`/`run_ask_stream` — ngay đầu:
  ```python
  cfg = await asyncio.to_thread(get_runtime_config)
  state = initial_state(request, resolved_mode=request.mode or cfg.retrieval_backend)
  state["runtime_config"] = cfg.model_dump()
  ```
  (đây cũng là nơi resolve `mode` per-câu-hỏi — xem khối "mode per-câu-hỏi" phía trên; KHÔNG
  đụng gì trong `nodes.py::retrieve()` cho phần resolve này). `initial_state()` đổi chữ ký
  thêm tham số `resolved_mode`, set `"requested_mode": resolved_mode` — TRƯỚC khi
  `graph.ainvoke`.
- **agent-service — `app/tools/graph_rag/vector_store.py::search_vector`**: đã có
  `top_k: int | None = None` — không cần đổi signature, chỉ cần nơi gọi truyền đúng giá trị.
- **agent-service — `app/tools/graph_rag/vector_store.py::search_dense_sparse`**: đã có
  `top_k` cho nhánh dense (limit tổng), nhưng nhánh sparse Prefetch đọc thẳng
  `settings.bm25_top_k` ([vector_store.py:172](apps/agent-service/app/tools/graph_rag/vector_store.py#L172))
  — thêm kwarg `bm25_top_k: int | None = None`, pattern `None → fallback settings.bm25_top_k`.
- **agent-service — `app/tools/graph_rag/graph_store.py::search_graph`**: thêm 6 kwarg
  optional mới (`max_seed_entities`, `max_chunks_per_seed`, `hub_source_count_threshold`,
  `max_context_items`, `max_path_hops`, `path_hit_weight` — 2 field cuối mới phát hiện vòng 6),
  áp dụng pattern "None → fallback `settings.X`" giống `top_k` đang có, tại đúng 6 chỗ hiện
  đọc `settings.graph_*` ([graph_store.py:253/261/283/328-329/391](apps/agent-service/app/tools/graph_rag/graph_store.py#L253)).
- **agent-service — `app/tools/traditional_rag/retriever.py::retrieve_traditional`**: đã có
  `top_k`; thêm 2 kwarg optional `bm25_top_k`, `rerank_top_k` (hiện đọc thẳng
  `get_settings().rerank_top_k` ở dòng cuối) forward xuống `search_dense_sparse`/cắt rerank.
- **agent-service — `app/tools/graph_rag/retriever.py::retrieve_graph`**: **hiện KHÔNG có
  kwarg tinh chỉnh nào** ngoài `seed_mentions` (và KHÔNG rerank — khác `retrieve_traditional`/
  `retrieve_hybrid`, giữ nguyên hành vi này, ngoài phạm vi plan) — thêm 7 kwarg optional
  (`graph_top_k` map vào `top_k` của `search_graph`, `graph_max_seed_entities`,
  `graph_max_chunks_per_seed`, `graph_hub_source_count_threshold`, `graph_max_context_items`,
  `graph_max_path_hops`, `graph_path_hit_weight`) forward xuống `search_graph`.
- **agent-service — `app/tools/hybrid/retriever.py::retrieve_hybrid`**: **KHÔNG cần
  `enable_vector`/`enable_graph`** (bản trước của plan giả định sai — dispatch 3 mode đã xảy
  ra Ở TẦNG `nodes.py::retrieve()`, hàm này CHỈ được gọi khi mode = `hybrid`, luôn cần cả
  vector lẫn graph). Thêm 10 kwarg optional (`rag_top_k`, `graph_top_k`, `hybrid_candidate_k`,
  `hybrid_rrf_k`, `rerank_top_k`, `bm25_top_k`, `graph_max_seed_entities`,
  `graph_max_chunks_per_seed`, `graph_hub_source_count_threshold`, `graph_max_context_items`,
  `graph_max_path_hops`, `graph_path_hit_weight` — 12 field, đều `None` mặc định);
  `hybrid_candidate_k`/`hybrid_rrf_k`/`rerank_top_k` resolve fallback `settings.X` ngay trong
  hàm (giống pattern có sẵn); các field còn lại forward xuống `_vector_candidates`/
  `_bm25_candidates`/`_graph_candidates` (cần thêm tham số tương ứng vào 3 hàm nội bộ này để
  chuyển tiếp vào `search_vector`/`search_bm25`/`search_graph`).
- **agent-service — `app/orchestrator/synthesis.py::stream_synthesis`**: thêm kwarg
  `temperature: float = 0.0`, dùng thay hằng số `0.0` hardcode trong
  `client.chat.completions.stream(...)`.
- **agent-service — `app/orchestrator/nodes.py`** (đọc `cfg = RuntimeConfig.model_validate(
  state["runtime_config"])` ở mỗi hàm cần, KHÔNG gọi lại `get_runtime_config()`):
  - `retrieve()`: **KHÔNG cần resolve mode ở đây nữa** (đã resolve trong `runner.py`, xem
    trên) — hàm này chỉ cần forward đúng subset tham số tinh chỉnh vào ĐÚNG 1-trong-3 hàm
    dispatch tuỳ `mode = state["requested_mode"]` (`traditional`/`graph`/`hybrid`, y hệt cấu
    trúc if/elif/else hiện có ở [nodes.py:184-193](apps/agent-service/app/orchestrator/nodes.py#L184-193),
    KHÔNG đổi cấu trúc dispatch, chỉ thêm kwarg vào mỗi nhánh gọi). `debug.retrieve.mode`
    ([nodes.py:200](apps/agent-service/app/orchestrator/nodes.py#L200)) ĐÃ sẵn là giá trị mode
    resolve — không cần thêm field debug mới.
  - `synthesize()`: `stream_synthesis(..., temperature=cfg.llm_temperature, batch_chars=
    cfg.stream_batch_chars)`. System prompt KHÔNG đụng ở đây — vẫn qua
    `get_active_prompt("synthesize", fallback=syn_prompt.SYSTEM_PROMPT)` như hiện tại (cơ chế
    riêng, xem quyết định 3b).
  - ~~`after_validate(state, config)`~~: **KHÔNG áp dụng** — node này hiện không tồn tại
    trong `graph.py` (xem quyết định 3c). Nếu sau này retry loop được làm lại, quay lại wire
    `synthesize_max_attempts` lúc đó — KHÔNG làm trong plan này.
  - `honest_answer()`/`direct_response()`: `emit_text_as_batches(text, emitter,
    cfg.stream_batch_chars)` thay cho `settings.stream_batch_chars`.
> **`tests/conftest.py::_DB_MODULES` (backend) phải thêm `"app.models.config"`** — cùng lý do
> đã ghi ở `backend-additions-plan.md` (đầu file, mọi model mới dùng `connection()` cần patch
> theo tên module, nếu không test GET/PUT config sẽ đọc/ghi bằng connection thật, không nằm
> trong transaction rollback của test).

- Test: backend — GET/PUT config, validate từng field ngoài range/enum sai bị từ chối (422)
  gồm cả constraint chéo `rerank_top_k <= hybrid_candidate_k`, `require_admin` chặn teacher;
  `mode` chấp nhận thiếu/`null` (không còn bắt buộc); agent-service — `get_runtime_config`
  fallback đúng khi bảng/kết nối lỗi; cache TTL: 2 lần gọi liên tiếp trong TTL chỉ query
  Postgres 1 lần (mock/patch counter, giống test có thể có sẵn cho `prompt_store`), gọi
  `clear_cache()` rồi gọi lại → query Postgres lần nữa; resolve mode trong `runner.py`:
  `request.mode` có giá trị → dùng đúng giá trị (bỏ qua `cfg.retrieval_backend`),
  `request.mode is None` → dùng `cfg.retrieval_backend`; `retrieve_traditional`/
  `retrieve_graph`/`retrieve_hybrid` mỗi hàm nhận đúng subset kwarg tinh chỉnh tương ứng
  (test bằng cách gán giá trị khác default, assert candidate/cutoff đổi theo);
  `retrieve_hybrid` KHÔNG còn cần test `enable_vector`/`enable_graph` (không tồn tại kwarg
  này — dispatch mode đã ở tầng `nodes.py::retrieve()`, ngoài `retrieve_hybrid`);
  `stream_synthesis` nhận đúng `temperature`; `synthesize()`/`honest_answer()`/
  `direct_response()` đọc đúng field từ `state["runtime_config"]` — test qua state giả
  (dict), KHÔNG cần Postgres thật, giữ agent-service test suite offline như hiện tại.

**Lưu ý ripple qua test có sẵn**:
- `tests/test_orchestrator_flow.py` + `tests/test_orchestrator_stream.py`: `_patch_retrieve`/
  `_patch_retrieve_traditional`/`_patch_retrieve_graph` (3 hàm mock riêng, khớp 3 module thật)
  đổi chữ ký chấp nhận `**kwargs` (không cần liệt kê hết field mới); `_patch_synthesize` đổi
  `async def fake(messages, *, emitter, model, batch_chars, temperature=0.0, client=None)`.
  Thêm bước set `state["runtime_config"] = RuntimeConfig().model_dump()` ở
  `initial_state`/trước khi gọi `run_ask`/`run_ask_stream` trong test, để mọi node đọc được
  giá trị mặc định thay vì `KeyError`. Test resolve mode ở `runner.py` (không phải
  `nodes.py::retrieve()` như bản trước của plan giả định).
- `tests/test_hybrid_retriever.py`: `_patch` hiện có `fake_graph(query, *, seed_mentions=None,
  **kw)` đã là catch-all — không cần đổi cho phần nhận tham số thừa; thêm test mới verify
  `retrieve_hybrid` forward đúng `rag_top_k`/`graph_top_k`/`bm25_top_k`/... xuống
  `search_vector`/`search_bm25`/`search_graph`, `hybrid_candidate_k`/`hybrid_rrf_k`/
  `rerank_top_k` đổi kết quả cutoff đúng khi truyền giá trị khác default. KHÔNG còn test
  `enable_vector`/`enable_graph` (kwarg này không tồn tại — xem trên); test 3-mode-dispatch
  (traditional chỉ gọi `retrieve_traditional`, graph chỉ gọi `retrieve_graph`, hybrid chỉ gọi
  `retrieve_hybrid`) nên viết ở `test_orchestrator_flow.py` cho `nodes.py::retrieve()`, không
  phải ở test của `retrieve_hybrid`.
- `tests/test_ask_schemas.py`: thêm test `AskRequest(mode=None)` parse hợp lệ (mặc định mới,
  khác hành vi cũ luôn ép `"hybrid"`), `AskRequest(mode="graph")` vẫn hợp lệ như cũ,
  `mode="bogus"` → `ValidationError`.
- `tests/test_orchestrator_flow.py` + `tests/test_orchestrator_stream.py`: thêm test cho hàm
  resolve mode ở `runner.py` (ví dụ tách thành helper `_resolve_mode(request, cfg)` cho dễ
  test đơn vị) — `request.mode` có giá trị KHÁC `cfg.retrieval_backend` → dùng giá trị request
  (override thắng); `request.mode is None` → dùng `cfg.retrieval_backend`. `nodes.py::retrieve()`
  bản thân KHÔNG cần test thêm gì cho phần resolve (nó chỉ đọc `state["requested_mode"]` đã
  resolve sẵn, y như hành vi hiện tại).

---

## Đề xuất chia nhỏ khi thực thi (nếu vẫn thấy to)

Có thể tách 3 lớp bên trong plan này, làm tuần tự, mỗi lớp tự test/dùng được:
1. **CRUD nền**: chỉ bảng `system_config` + `models/config.py` + `api/config.py` phía
   backend. Agent-service CHƯA đọc gì — admin xem/sửa được config nhưng chưa có tác dụng.
2. **Wiring synthesize**: agent-service đọc `runtime_config`, áp `llm_temperature`/
   `stream_batch_chars` vào `synthesize`/`honest_answer`/`direct_response`. Không đụng
   retrieval, không đụng prompt (đã quản lý riêng qua `prompt_store`), không đụng retry
   (`after_validate` hiện không tồn tại, xem quyết định 3c).
3. **Wiring retrieval + fallback mode**: `retrieve_traditional`/`retrieve_graph`/
   `retrieve_hybrid`/`graph_store.py`/`vector_store.py` (12 tham số tinh chỉnh, mỗi hàm nhận
   đúng subset của nó) + nới field `AskRequest.mode` thành nullable + resolve fallback trong
   `runner.py`. Đụng đường retrieval của MỌI câu hỏi — test kỹ nhất trong 3 lớp.

---

## Frontend — spec (đối chiếu code thật — vòng 6, 2026-07-06)

**Phát hiện quan trọng**: `docs/plan/frontend-plan.md` (mục A2, Pha C3) claim
`RetrievalModeSelect` "CHƯA build", nhưng đối chiếu code thật thì **dropdown chọn mode ĐÃ TỒN
TẠI VÀ ĐANG CHẠY** — [`Composer.tsx:4-8,40-56`](apps/frontend/src/features/chat/Composer.tsx#L4-56):
select "Cách truy hồi" với 3 option (Kết hợp/Vector/Đồ thị, giá trị `hybrid`/`traditional`/
`graph`), hiển thị cho MỌI role, gửi kèm `mode` vào mỗi request qua `useChat.ts`. Cả
`frontend-plan.md` LẪN bản trước của `system-config-plan.md` đều lệch so với thực tế trên
điểm này — nên cân nhắc cập nhật luôn `frontend-plan.md` khi có dịp (ngoài phạm vi sửa của
file này). Vì đã có sẵn, phần việc FE thật sự còn lại **nhỏ hơn nhiều** so với spec cũ dưới
đây: chỉ cần (a) thêm 1 option "Mặc định hệ thống" map sang gửi `undefined` thay vì 1 trong 3
giá trị cứng, (b) đổi giá trị khởi tạo mặc định (hiện `useChat` presumably khởi tạo cứng
`"hybrid"`) sang option mới này. Spec đầy đủ dưới đây giữ để build đúng khi tới lượt.

### `RetrievalModeSelect` — mọi user, trong khung chat (đã có 3/4 option, thiếu 1)
Đặt cạnh ô nhập câu hỏi trong `Composer` (đã đúng vị trí) — dropdown/segmented control **4**
lựa chọn (hiện chỉ có 3, xem trên): **"Mặc định hệ thống"** (MỚI — gửi `mode: undefined` —
dùng mặc định admin đã đặt) / **"Traditional RAG"** (đã có, label hiện "Vector") /
**"GraphRAG"** (đã có, label hiện "Đồ thị") / **"Hybrid"** (đã có, label hiện "Kết hợp").
Chọn giá trị nào gửi kèm giá trị đó vào `POST .../ask`, **chỉ áp dụng cho đúng câu hỏi đang
gửi** — không đổi mặc định hệ thống, không lưu lại cho câu hỏi sau (mỗi câu hỏi tự chọn lại,
mặc định luôn quay về "Mặc định hệ thống" thay vì hiện đang cứng "Kết hợp"). Value đã lưu tạm
trong state cục bộ `useState<RetrievalMode>` ở [`ChatPanel.tsx:25`](apps/frontend/src/features/chat/ChatPanel.tsx#L25)
(không persist) — giữ nguyên cơ chế này, chỉ cần đổi type thành `RetrievalMode | undefined`
và giá trị khởi tạo từ `"hybrid"` sang `undefined`. Hiển thị cho **MỌI role**, không ẩn với
user thường (khác `DebugPanel`).

### `DebugPanel` — KHÔNG cần thêm field
Đã hiện sẵn — [`DebugPanel.tsx:91`](apps/frontend/src/features/chat/DebugPanel.tsx#L91):
`<Row label="Chế độ truy hồi" value={item.retrievalMode ?? "—"} />`, đọc từ
`debug.retrieve.mode`/`retrieval_mode` đã resolve. Không có việc gì phải làm ở đây kể cả sau
khi thêm fallback admin default — giá trị hiển thị vẫn luôn là mode ĐÃ RESOLVE.

### Tab Cấu hình hệ thống (admin, `/admin/advanced`) ⭐ áp dụng LIVE
Khác hẳn Module 5 (read-only): đây là **form ghi**, có hiệu lực thật ngay khi lưu. Không quản
lý model. `ConfigForm` đọc `GET /api/admin/config`, chia 3 nhóm:
- **Chế độ truy xuất mặc định**: `RadioGroup`/`Select` 1 trong 3 — "Traditional RAG (chỉ
  vector)" / "GraphRAG (chỉ đồ thị)" / "Hybrid (cả hai — mặc định)" (`retrieval_backend` —
  tên field trong `system_config`; ở tầng `AskRequest`/FE field tương ứng tên là `mode`).
  Helper text: "Áp dụng cho câu hỏi nào user không tự chọn mode riêng (chọn 'Mặc định hệ
  thống' ở khung chat)." Đổi mode không xoá code 2 mode còn lại, chỉ đổi mode MẶC ĐỊNH cho
  lượt hỏi tiếp theo.
- **Nhóm Retrieval** (số nguyên dương, mỗi field kèm giá trị mặc định gợi ý trong helper
  text): `rag_top_k` (20), `graph_top_k` (20), `hybrid_candidate_k` (30), `hybrid_rrf_k`
  (60), `rerank_top_k` (8), `bm25_top_k` (20), `graph_max_seed_entities` (5),
  `graph_max_chunks_per_seed` (20), `graph_hub_source_count_threshold` (80),
  `graph_max_context_items` (12), `graph_max_path_hops` (3), `graph_path_hit_weight` (1.5,
  số thực). Validate client-side: `rerank_top_k <= hybrid_candidate_k` (khớp DB CHECK), báo
  lỗi ngay dưới ô nếu vi phạm.
- **Nhóm Synthesize**: slider/số **Temperature** (`llm_temperature`, 0.0–2.0); số **Ngưỡng
  ký tự mỗi batch stream** (`stream_batch_chars`, >0). KHÔNG có ô "Số lần thử lại tối đa" —
  `synthesize_max_attempts` bỏ khỏi scope (quyết định 3c, cơ chế retry hiện không tồn tại).
  KHÔNG có ô sửa system prompt ở đây — việc đó đã có trang riêng `/admin/prompts` (version +
  rollback thật, xem quyết định 3b) để tránh 2 chỗ ghi đè cùng 1 prompt gây nhầm lẫn.
- Nút **"Lưu & áp dụng"** → `PUT /api/admin/config`. Sau khi lưu thành công, hiện banner xác
  nhận: "Đã lưu — có hiệu lực trong tối đa 60 giây (cache nội bộ agent-service)." (KHÔNG hứa
  "câu hỏi tiếp theo" tức thời tuyệt đối, vì `get_runtime_config()` có TTL cache ~60s giống
  `prompt_store`, xem §Backend/Agent-service).
- Field **KHÔNG có** trong form: chọn/đổi model, đổi embedding model, ngưỡng hỏi lại/từ chối
  dạng số, sửa system prompt (quản lý ở `/admin/prompts` riêng).

### Testing (frontend, khi build)
- `RetrievalModeSelect` (3 option đã có test/hoạt động sẵn — chỉ thêm test cho option MỚI):
  chọn "Mặc định hệ thống" → request gửi `mode: undefined`; 3 option cũ (Traditional/GraphRAG/
  Hybrid) giữ nguyên hành vi hiện có (gửi đúng giá trị); reset về "Mặc định hệ thống" ở câu
  hỏi kế tiếp thay vì reset về "Hybrid" như hiện tại.
- `ConfigForm`: validate `llm_temperature` trong [0,2], `rerank_top_k <= hybrid_candidate_k`;
  banner "Đã lưu — có hiệu lực trong tối đa 60 giây" hiện sau `PUT` thành công.

### Verification (khi build xong, thêm vào flow chung của `frontend-plan.md`)
> Lưu ý: do TTL cache ~60s ở `get_runtime_config()`, các bước "lưu → hỏi câu tiếp theo" dưới
> đây có thể cần đợi tới 60s (hoặc gọi `clear_cache()` thủ công trong test) mới thấy hiệu lực,
> KHÔNG phải tức thời ngay sau khi `PUT` trả 200.
1. Chọn mode mặc định "Traditional RAG" ở tab Cấu hình, lưu, đợi cache hết hạn (≤60s) → hỏi
   câu tiếp theo (chọn "Mặc định hệ thống" ở `RetrievalModeSelect`, option mới) → DebugPanel
   (đã có sẵn `Row label="Chế độ truy hồi"`) thấy giá trị `traditional`.
2. Cùng lúc đó, tự chọn "GraphRAG" ở `RetrievalModeSelect` cho 1 câu hỏi khác → override
   thắng ngay (KHÔNG phụ thuộc TTL cache vì đây là field per-request, không qua
   `system_config`), DebugPanel hiện `graph` dù mặc định hệ thống đang là "Traditional RAG"
   (verify đúng thứ tự ưu tiên override > mặc định — hành vi này vốn đã hoạt động đúng cho 3
   mode cụ thể từ trước, chỉ verify thêm case "Mặc định hệ thống" mới).
3. Đổi `llm_temperature`, lưu, đợi cache hết hạn (≤60s) → câu tiếp theo dùng giá trị mới.
4. Giảm `rag_top_k`/`graph_top_k`/`bm25_top_k` xuống thấp → DebugPanel thấy số `chunks`/
   `graph_context` giảm theo (tuỳ mode đang chạy).
5. Nhập `llm_temperature` ngoài [0,2] hoặc `rerank_top_k > hybrid_candidate_k` → bị chặn (422).
