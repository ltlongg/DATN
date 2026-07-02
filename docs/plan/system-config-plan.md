# Plan System Config — Cấu hình hệ thống (retrieval + synthesize, áp dụng LIVE)

## Context

Tách riêng khỏi `docs/plan/backend-additions-plan.md` (2026-07-01) vì đây là phần **nặng và
rủi ro nhất** trong Module 4 admin nâng cao — đụng nhiều file orchestrator đang chạy ổn định
(`state.py`, `runner.py`, `nodes.py` cả 5 hàm, `retriever.py`, `graph_store.py`,
`vector_store.py`, `synthesis.py`) cả phía backend lẫn agent-service lẫn frontend.

**Thứ tự làm**: **SAU KHI** hoàn thiện xong 4 phần trong `backend-additions-plan.md` (Debug
streaming, KB Inspector, Hội thoại & chất lượng, Người dùng & quota). Frontend tab Cấu hình
hệ thống trong lúc đó hiện **"Sắp cập nhật"** (xem `frontend-plan.md` Pha C — đã đổi thành
stub, trỏ về plan này). Có plan sẵn ở đây để khi tới lượt làm thì cứ theo mà code, không phải
thiết kế lại từ đầu.

> **Thuật ngữ**: role không-phải-admin gọi là **"user"** ở mô tả; **giá trị literal trong
> code vẫn là `teacher`**.

---

## Quyết định đã chốt (4 vòng, vòng 3+4 sửa lại vòng 1)

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
2. KHÔNG quản lý model (bỏ hẳn `llm_model_override`).
3. Quản lý HẾT các tham số tinh chỉnh khác đang nằm trong `app/core/config.py::Settings` —
   cả phía **retrieval** (rag_top_k, graph_top_k, hybrid_candidate_k, hybrid_rrf_k,
   rerank_top_k, graph_max_seed_entities, graph_max_chunks_per_seed,
   graph_hub_source_count_threshold, graph_max_context_items) lẫn phía **synthesize**
   (temperature, prompt override, synthesize_max_attempts, stream_batch_chars). Riêng 9
   field tinh chỉnh retrieval + 4 field synthesize KHÔNG có bản override per-câu-hỏi —
   chỉ `retrieval_backend` mới cần override per-câu-hỏi (vì đây là lựa chọn mà USER — không
   chỉ admin — quan tâm trực tiếp: "muốn hỏi kiểu tra cứu văn bản hay theo quan hệ nhân
   vật/sự kiện").

**Nguyên tắc riêng cho nhóm này**: đây KHÔNG phải trình xem read-only kiểu Module 5. Khi
admin bấm lưu, giá trị phải **áp dụng thật vào agent-service ngay lượt hỏi tiếp theo** —
không cần restart, không cache.

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

**Đọc 1 LẦN mỗi REQUEST, lưu vào `state` — không cache qua các request, không đọc N lần
trong 1 request**: nếu để mỗi node (`retrieve`, `synthesize`, `after_validate`,
`honest_answer`, `direct_response`) tự gọi `get_runtime_config()` riêng thì MỘT câu hỏi tốn
tới 5 lượt round-trip Postgres, và `after_validate` là **conditional edge SYNC** (không async)
nên gọi `psycopg` chặn trực tiếp ở đó dễ block event loop. Giải pháp: đọc config đúng **1 lần
ở đầu request** (`run_ask`/`run_ask_stream`, trước khi vào graph), nhét vào
`AgentState["runtime_config"]` (dict), mọi node sau chỉ ĐỌC từ `state` — không I/O gì thêm.
Vẫn giữ đúng yêu cầu "không cache": mỗi CÂU HỎI MỚI đọc lại Postgres mới nhất; chỉ tránh đọc
lặp lại NHIỀU LẦN cho CÙNG một câu hỏi.

**`retrieval_backend` override per-câu-hỏi (user, mọi role) — thiết kế 2 lớp**:
Khác các field còn lại (chỉ admin chỉnh qua `/api/admin/config`), `retrieval_backend` còn có
đường đi thứ 2: user tự chọn NGAY TRONG khung chat cho từng câu hỏi, giống hệt cơ chế field
`debug` hiện có trên `AskRequest` (per-request, không lưu thành mặc định chung).

1. **agent-service — `app/schemas/ask.py::AskRequest`**: thêm field
   `retrieval_backend: Literal["traditional", "graph", "hybrid"] | None = None` (`None` =
   không override, dùng mặc định từ `system_config`).
2. **backend — `app/schemas/chat.py::AskRequest`** (frontend → backend): thêm field mirror
   y hệt; **backend KHÔNG gác role** ở field này (khác `debug` — field này mọi role dùng
   được, không riêng admin). `apps/backend/app/services/agent_client.py::AgentAskRequest`
   thêm field tương ứng, forward nguyên giá trị sang agent-service.
3. **agent-service — `app/orchestrator/state.py::AgentState`**: thêm field
   `retrieval_backend_override: Literal["traditional", "graph", "hybrid"] | None`.
4. **agent-service — `app/orchestrator/runner.py::initial_state`**: set
   `"retrieval_backend_override": request.retrieval_backend` (mirror cách `question`/
   `history` đã được set từ `request`).
5. **agent-service — `app/orchestrator/nodes.py::retrieve()`**: mode thật sự dùng =
   `state.get("retrieval_backend_override") or cfg.retrieval_backend` (override thắng nếu
   có, không thì rơi về mặc định admin đặt). Đưa giá trị ĐÃ RESOLVE (không phải override
   thô) vào `debug.retrieve.retrieval_backend` để admin thấy đúng mode nào thật sự chạy.
6. Test: agent-service — `retrieve()` ưu tiên `retrieval_backend_override` khi có, rơi về
   `cfg.retrieval_backend` khi `None`; backend — field `retrieval_backend` không bị ép/lọc
   theo role (khác `debug`), request sai enum → 422 từ Pydantic (không cần validate tay).

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
    -- synthesize
    llm_temperature                  REAL NOT NULL DEFAULT 0.0
                                         CHECK (llm_temperature >= 0 AND llm_temperature <= 2),
    synthesize_prompt_override       TEXT,
    synthesize_max_attempts          INTEGER NOT NULL DEFAULT 2   CHECK (synthesize_max_attempts >= 1),
    stream_batch_chars               INTEGER NOT NULL DEFAULT 160 CHECK (stream_batch_chars > 0),
    updated_at                       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (rerank_top_k <= hybrid_candidate_k)  -- rerank cắt TỪ pool đã fuse, không thể lớn hơn pool
);
INSERT INTO system_config (id) VALUES (1) ON CONFLICT (id) DO NOTHING;
```

**Field nào wiring thật, field nào KHÔNG làm (nói rõ để khỏi nửa vời)**:
| Field | Áp dụng vào đâu | Ghi chú |
|-------|------------------|---------|
| `retrieval_backend` (`traditional`\|`graph`\|`hybrid`, mặc định hệ thống) | `nodes.py::retrieve()` suy ra `enable_vector`/`enable_graph` rồi truyền vào `retrieve_hybrid(..., enable_vector=, enable_graph=)`; **user override được per-câu-hỏi** qua `AskRequest.retrieval_backend` (xem khối "override per-câu-hỏi" phía trên) | `traditional`→chỉ vector; `graph`→chỉ graph; `hybrid`→cả hai (mặc định, = hành vi hiện tại). 3 mode LUÔN có sẵn; admin đặt mặc định hệ thống, user chọn khác cho câu hỏi của mình — KHÔNG xoá code của 2 mode còn lại |
| `rag_top_k` | `search_vector(question, top_k=)` — **đã có sẵn seam** `top_k: int \| None = None` trong `vector_store.py`, chỉ cần truyền xuống từ `retrieve_hybrid` | |
| `graph_top_k` | `search_graph(query, top_k=)` — **đã có sẵn seam** tương tự trong `graph_store.py` | |
| `hybrid_candidate_k` / `hybrid_rrf_k` / `rerank_top_k` | đọc trực tiếp `settings.X` bên trong `retrieve_hybrid` hiện tại — cần thêm 3 kwarg optional (`None` = fallback `settings.X`, giữ tương thích ngược) | |
| `graph_max_seed_entities` / `graph_max_chunks_per_seed` / `graph_hub_source_count_threshold` / `graph_max_context_items` | đọc trực tiếp `settings.X` bên trong `search_graph` (graph_store.py dòng 221/229/251/309) — cần thêm 4 kwarg optional mới, cùng pattern `None → fallback settings.X` | |
| `llm_temperature` | `stream_synthesis(..., temperature=)` — LLM call synthesize | build_query GIỮ NGUYÊN `temperature=0.0` cứng (không cho chỉnh) — cần deterministic cho routing/rewrite, đổi ở đây dễ phá route/entity extraction |
| `synthesize_prompt_override` | thay `SYSTEM_PROMPT` của `app/prompts/synthesize.py` trong node `synthesize` | Ghi đè TOÀN VĂN. **CHƯA có version history/rollback** — để trống = quay lại prompt mặc định trong code |
| `synthesize_max_attempts` | `after_validate()` — điều kiện retry synthesize | |
| `stream_batch_chars` | `synthesize()`, `honest_answer()`, `direct_response()` — cùng 1 tham số batching hiện dùng ở cả 3 chỗ | |
| ~~model (`llm_model`/`orchestrator_llm_model`/...)~~ | KHÔNG đưa vào config | Chốt vòng 2: không quản lý model |
| ~~`embedding_model`/`chunk_size`/`qdrant_collection`~~ | KHÔNG đưa vào config | Đây là tham số INDEX-TIME — đổi mà không re-index sẽ desync với dữ liệu đã index, ngoài phạm vi "áp dụng live" |
| ~~`ask_max_question_chars`/`ask_max_history_messages`~~ | KHÔNG đưa vào config | Bị "đóng băng" ở tầng Pydantic `Field(max_length=...)` lúc định nghĩa class (cả backend lẫn agent-service) — muốn sửa live cần đổi sang custom validator đọc config mỗi lần, việc khác/lớn hơn, để đợt sau |
| ~~ngưỡng hỏi lại/từ chối (số)~~ | KHÔNG đưa vào config | `confidence`/`route` là categorical do LLM structured-output quyết định, không phải so sánh ngưỡng số |

- **backend — `app/models/config.py`** (mới): `SystemConfig` pydantic (14 field trên, gồm
  `retrieval_backend: Literal["traditional","graph","hybrid"]`) + `get_config()` +
  `update_config(fields: dict)`. Validate range/enum ở tầng Pydantic schema TRƯỚC khi update
  (khớp các CHECK ở DB); DB CHECK là lưới an toàn cuối — map `psycopg.errors.CheckViolation`
  → `AppError(422, "validation_error", ...)` nếu lọt qua.
- **backend — `app/schemas/config.py`** + **`app/api/config.py`** (prefix
  `/api/admin/config`, `require_admin`): `GET /api/admin/config`, `PUT /api/admin/config`
  (`exclude_unset` cho phép sửa từng phần). Đăng ký `main.py`.
- **agent-service — `app/core/runtime_config.py`** (mới): `RuntimeConfig` pydantic (default =
  y hệt `Settings` hiện tại) + `get_runtime_config(database_url=None) -> RuntimeConfig` —
  `psycopg.connect` trực tiếp (cùng pattern `_database_url()` như `chunk_store.py`). Bắt
  `psycopg.errors.UndefinedTable` + `psycopg.OperationalError` → trả `RuntimeConfig()` mặc
  định (agent-service KHÔNG sập nếu backend chưa `init_db.py` hoặc mất kết nối tạm thời).
- **agent-service — `app/orchestrator/state.py::AgentState`**: thêm field
  `runtime_config: dict[str, object]` (overwrite thường, KHÔNG cần reducer — ghi 1 lần đầu
  request, chỉ đọc sau đó).
- **agent-service — `app/orchestrator/runner.py`**: `run_ask`/`run_ask_stream` — ngay đầu,
  `cfg = await asyncio.to_thread(get_runtime_config)`; `state = initial_state(request)`;
  `state["runtime_config"] = cfg.model_dump()` — TRƯỚC khi `graph.ainvoke`.
- **agent-service — `app/tools/graph_rag/vector_store.py::search_vector`**: đã có
  `top_k: int | None = None` — không cần đổi signature, chỉ cần nơi gọi truyền đúng giá trị.
- **agent-service — `app/tools/graph_rag/graph_store.py::search_graph`**: thêm 4 kwarg
  optional mới (`max_seed_entities`, `max_chunks_per_seed`, `hub_source_count_threshold`,
  `max_context_items`, đều `int | None = None`), áp dụng pattern "None → fallback
  `settings.X`" giống `top_k` đang có, tại đúng 4 chỗ hiện đọc `settings.graph_*`
  (dòng 221/229/251/309).
- **agent-service — `app/tools/hybrid/retriever.py::retrieve_hybrid`**: thêm kwarg
  `enable_vector: bool = True, enable_graph: bool = True` (mode selector — nhánh nào tắt thì
  bỏ qua gọi candidate tương ứng, KHÔNG raise lỗi/không thêm warning vì đây là chủ ý admin
  chọn mode, khác lỗi backend chết thật; dùng 2 helper `_empty_vector()`/`_empty_graph()`
  trả `([], None)`/`([], [], None)` để giữ nguyên logic `asyncio.gather` + cách tính
  `warnings` hiện có) + 9 kwarg optional (`rag_top_k`, `graph_top_k`, `hybrid_candidate_k`,
  `hybrid_rrf_k`, `rerank_top_k`, `graph_max_seed_entities`, `graph_max_chunks_per_seed`,
  `graph_hub_source_count_threshold`, `graph_max_context_items`, đều `None` mặc định);
  `hybrid_candidate_k`/`hybrid_rrf_k`/`rerank_top_k` resolve fallback `settings.X` ngay trong
  hàm (giống pattern có sẵn); các field còn lại forward xuống `_vector_candidates`/
  `_graph_candidates` (cần thêm tham số tương ứng vào 2 hàm nội bộ này để chuyển tiếp vào
  `search_vector`/`search_graph`).
- **agent-service — `app/orchestrator/synthesis.py::stream_synthesis`**: thêm kwarg
  `temperature: float = 0.0`, dùng thay hằng số `0.0` hardcode trong
  `client.chat.completions.stream(...)`.
- **agent-service — `app/orchestrator/nodes.py`** (đọc `cfg = RuntimeConfig.model_validate(
  state["runtime_config"])` ở mỗi hàm cần, KHÔNG gọi lại `get_runtime_config()`):
  - `retrieve()`: resolve `mode = state.get("retrieval_backend_override") or
    cfg.retrieval_backend` (override của user cho câu hỏi này thắng, không thì dùng mặc định
    admin đặt); suy `enable_vector = mode in ("traditional", "hybrid")`,
    `enable_graph = mode in ("graph", "hybrid")`; truyền 2 field này + toàn bộ 9 field tinh
    chỉnh retrieval vào `retrieve_hybrid(...)`. Thêm `mode` (giá trị ĐÃ RESOLVE) vào
    `debug.retrieve.retrieval_backend` (cơ chế debug đã có ở `backend-additions-plan.md` §1)
    để admin thấy đúng mode nào thật sự chạy cho lượt hỏi đó, kể cả khi user đã tự override.
  - `synthesize()`: `stream_synthesis(..., temperature=cfg.llm_temperature, batch_chars=
    cfg.stream_batch_chars)`; system prompt = `cfg.synthesize_prompt_override or
    syn_prompt.SYSTEM_PROMPT`.
  - `after_validate(state, config)`: **verify trong lúc code** LangGraph
    `add_conditional_edges` có cho conditional-edge-fn nhận thêm `config`/đọc `state` hay
    không (tra docs LangGraph, đừng giả định) — dùng `state.get("synthesize_attempt_count",
    0) < cfg.synthesize_max_attempts` thay cho `settings.synthesize_max_attempts`. Vì chỉ
    đọc dict có sẵn trong `state`, KHÔNG có I/O nên an toàn dù hàm là sync.
  - `honest_answer()`/`direct_response()`: `emit_text_as_batches(text, emitter,
    cfg.stream_batch_chars)` thay cho `settings.stream_batch_chars`.
> **`tests/conftest.py::_DB_MODULES` (backend) phải thêm `"app.models.config"`** — cùng lý do
> đã ghi ở `backend-additions-plan.md` (đầu file, mọi model mới dùng `connection()` cần patch
> theo tên module, nếu không test GET/PUT config sẽ đọc/ghi bằng connection thật, không nằm
> trong transaction rollback của test).

- Test: backend — GET/PUT config, validate từng field ngoài range/enum sai bị từ chối (422)
  gồm cả constraint chéo `rerank_top_k <= hybrid_candidate_k`, `require_admin` chặn teacher;
  agent-service — `get_runtime_config` fallback đúng khi bảng/kết nối lỗi; `search_graph`
  nhận đúng 4 override mới; `retrieve_hybrid` với `retrieval_backend="traditional"` → KHÔNG
  gọi `search_graph` (chỉ vector), `="graph"` → KHÔNG gọi `search_vector` (chỉ graph),
  `="hybrid"` → gọi cả hai (mặc định, hành vi y hệt hiện tại); forward đúng 9 field tinh
  chỉnh xuống `search_vector`/`search_graph`/RRF math (test bằng cách gán giá trị khác
  default, assert candidate/cutoff đổi theo); `stream_synthesis` nhận đúng `temperature`;
  `synthesize()`/`after_validate()`/`honest_answer()`/`direct_response()` đọc đúng field từ
  `state["runtime_config"]` — test qua state giả (dict), KHÔNG cần Postgres thật, giữ agent-
  service test suite offline như hiện tại.

**Lưu ý ripple qua test có sẵn**:
- `tests/test_orchestrator_flow.py` + `tests/test_orchestrator_stream.py`: `_patch_retrieve`
  đổi `async def fake(question, *, seed_mentions=None, **kwargs)` (chấp nhận mọi kwarg mới,
  không cần liệt kê hết); `_patch_synthesize` đổi `async def fake(messages, *, emitter,
  model, batch_chars, temperature=0.0, client=None)`. Thêm bước set
  `state["runtime_config"] = RuntimeConfig().model_dump()` (hoặc override cụ thể) ở
  `initial_state`/trước khi gọi `run_ask`/`run_ask_stream` trong test, để mọi node đọc được
  giá trị mặc định thay vì `KeyError`.
- `tests/test_hybrid_retriever.py`: `_patch` hiện có `fake_graph(query, *, seed_mentions=None,
  **kw)` đã là catch-all — không cần đổi cho phần nhận tham số thừa; thêm test mới verify
  `retrieve_hybrid` forward đúng `rag_top_k`/`graph_top_k`/... xuống `search_vector`/
  `search_graph`, `hybrid_candidate_k`/`hybrid_rrf_k`/`rerank_top_k` đổi kết quả cutoff đúng
  khi truyền giá trị khác default, và 3 test mode: `enable_graph=False` → `search_graph`
  KHÔNG được gọi (assert qua counter) + kết quả chỉ có nguồn `"vector"`; `enable_vector=False`
  tương tự cho `search_vector`; mặc định (cả hai `True`) giữ nguyên mọi test hybrid hiện có.
- `tests/test_ask_schemas.py`: thêm test `AskRequest(retrieval_backend="graph")` parse hợp
  lệ, `retrieval_backend="bogus"` → `ValidationError`; `retrieval_backend` vắng mặt → mặc
  định `None` (không phá test cũ vốn không truyền field này).
- `tests/test_orchestrator_flow.py` + `tests/test_orchestrator_stream.py`: thêm test
  `retrieve()` ưu tiên `state["retrieval_backend_override"]` khi request có set (khác với
  `cfg.retrieval_backend` mặc định) — set cả hai giá trị KHÁC NHAU trong test để phân biệt
  rõ override thắng, không phải trùng hợp đọc nhầm field.

---

## Đề xuất chia nhỏ khi thực thi (nếu vẫn thấy to)

Có thể tách 3 lớp bên trong plan này, làm tuần tự, mỗi lớp tự test/dùng được:
1. **CRUD nền**: chỉ bảng `system_config` + `models/config.py` + `api/config.py` phía
   backend. Agent-service CHƯA đọc gì — admin xem/sửa được config nhưng chưa có tác dụng.
2. **Wiring synthesize**: agent-service đọc `runtime_config`, áp `llm_temperature`/
   `synthesize_prompt_override`/`synthesize_max_attempts`/`stream_batch_chars` vào
   `synthesize`/`honest_answer`/`direct_response`/`after_validate`. Không đụng retrieval.
3. **Wiring retrieval + chọn mode**: `retriever.py`/`graph_store.py`/`vector_store.py` +
   field `AskRequest.retrieval_backend` (override per-câu-hỏi) + 9 tham số tinh chỉnh. Đụng
   đường retrieval của MỌI câu hỏi — test kỹ nhất trong 3 lớp.

---

## Frontend — spec (chưa build, giữ tham khảo)

`docs/plan/frontend-plan.md` hiện đã đổi tab Cấu hình + `RetrievalModeSelect` thành stub
"Sắp cập nhật" (xem Pha C ở đó). Spec chi tiết dưới đây giữ lại để build đúng khi tới lượt,
KHÔNG cần thiết kế lại UI từ đầu.

### `RetrievalModeSelect` — mọi user, trong khung chat (không phải trang admin)
Đặt cạnh ô nhập câu hỏi trong `Composer` — dropdown/segmented control 4 lựa chọn:
**"Mặc định hệ thống"** (gửi `retrieval_backend: undefined` — dùng mặc định admin đã đặt) /
**"Traditional RAG"** / **"GraphRAG"** / **"Hybrid"**. Chọn giá trị nào gửi kèm giá trị đó
vào `POST .../ask`, **chỉ áp dụng cho đúng câu hỏi đang gửi** — không đổi mặc định hệ thống,
không lưu lại cho câu hỏi sau (mỗi câu hỏi tự chọn lại, mặc định luôn quay về "Mặc định hệ
thống"). Value lưu tạm trong `chatUiStore` (không persist). Hiển thị cho **MỌI role**, không
ẩn với user thường (khác `DebugPanel`).

### `DebugPanel` — thêm field
Block "Retrieval" trong debug panel thêm `retrieval_backend` (mode ĐÃ RESOLVE thật sự chạy,
phản ánh cả trường hợp user tự chọn mode khác mặc định hệ thống).

### Tab Cấu hình hệ thống (admin, `/admin/advanced`) ⭐ áp dụng LIVE
Khác hẳn Module 5 (read-only): đây là **form ghi**, có hiệu lực thật ngay khi lưu. Không quản
lý model. `ConfigForm` đọc `GET /api/admin/config`, chia 3 nhóm:
- **Chế độ truy xuất mặc định**: `RadioGroup`/`Select` 1 trong 3 — "Traditional RAG (chỉ
  vector)" / "GraphRAG (chỉ đồ thị)" / "Hybrid (cả hai — mặc định)" (`retrieval_backend`).
  Helper text: "Áp dụng cho câu hỏi nào user không tự chọn mode riêng." Đổi mode không xoá
  code 2 mode còn lại, chỉ đổi mode MẶC ĐỊNH cho lượt hỏi tiếp theo.
- **Nhóm Retrieval** (số nguyên dương, mỗi field kèm giá trị mặc định gợi ý trong helper
  text): `rag_top_k` (20), `graph_top_k` (20), `hybrid_candidate_k` (30), `hybrid_rrf_k`
  (60), `rerank_top_k` (8), `graph_max_seed_entities` (5), `graph_max_chunks_per_seed` (20),
  `graph_hub_source_count_threshold` (80), `graph_max_context_items` (12). Validate
  client-side: `rerank_top_k <= hybrid_candidate_k` (khớp DB CHECK), báo lỗi ngay dưới ô nếu
  vi phạm.
- **Nhóm Synthesize**: slider/số **Temperature** (`llm_temperature`, 0.0–2.0); số **Số lần
  thử lại tối đa** (`synthesize_max_attempts`, ≥1); số **Ngưỡng ký tự mỗi batch stream**
  (`stream_batch_chars`, >0); textarea **System prompt override**
  (`synthesize_prompt_override`) — để trống = dùng prompt mặc định trong code. Cảnh báo rõ
  trên textarea: "Ghi đè toàn văn, KHÔNG có lịch sử/rollback — để quay lại mặc định, xoá
  trắng ô này."
- Nút **"Lưu & áp dụng ngay"** → `PUT /api/admin/config`. Sau khi lưu thành công, hiện banner
  xác nhận: "Đã áp dụng — câu hỏi tiếp theo của mọi user (không tự override) sẽ dùng cấu
  hình mới."
- Field **KHÔNG có** trong form: chọn/đổi model, đổi embedding model, ngưỡng hỏi lại/từ chối
  dạng số, version history/rollback prompt.

### Testing (frontend, khi build)
- `RetrievalModeSelect`: hiển thị cho MỌI role; chọn "Mặc định hệ thống" → request gửi
  `retrieval_backend: undefined`; chọn mode cụ thể → gửi đúng giá trị, reset về mặc định ở
  câu hỏi kế tiếp.
- `ConfigForm`: validate `llm_temperature` trong [0,2], `rerank_top_k <= hybrid_candidate_k`;
  banner "Đã áp dụng" hiện sau `PUT` thành công.

### Verification (khi build xong, thêm vào flow chung của `frontend-plan.md`)
1. Chọn mode mặc định "Traditional RAG" ở tab Cấu hình, lưu → hỏi câu tiếp theo (chọn "Mặc
   định hệ thống" ở `RetrievalModeSelect`) → DebugPanel thấy `graph_context = 0`.
2. Cùng lúc đó, tự chọn "GraphRAG" ở `RetrievalModeSelect` cho 1 câu hỏi khác → override
   thắng, `chunks` chỉ đến từ graph dù mặc định hệ thống đang là "Traditional RAG" (verify
   đúng thứ tự ưu tiên override > mặc định).
3. Đổi `llm_temperature`, lưu → câu tiếp theo dùng giá trị mới. Nhập `synthesize_prompt_override`
   → câu trả lời đổi giọng văn; xoá trắng → quay lại prompt mặc định.
4. Giảm `rag_top_k`/`graph_top_k` xuống thấp → DebugPanel thấy số `chunks`/`graph_context`
   giảm theo.
5. Nhập `llm_temperature` ngoài [0,2] hoặc `rerank_top_k > hybrid_candidate_k` → bị chặn (422).
