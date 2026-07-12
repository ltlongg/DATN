# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

Đồ án tốt nghiệp: **Agentic RAG cho lịch sử Việt Nam** (giai đoạn Pháp thuộc → thống nhất đất nước), dành cho giáo viên. Hệ thống hỏi đáp tiếng Việt có căn cứ từ tài liệu, kết hợp **traditional RAG + GraphRAG + hybrid retrieval**, có khả năng render câu trả lời lên **bản đồ Việt Nam + timeline** khi sự kiện có dữ liệu thời gian/địa điểm.

Dataset chính: `lichsu.clean.md` (~3.1MB, 7.623 dòng) — bản đã preprocess của `lichsu.md`. Đã chunk thành `dataset/chunks_llm.json` (1213 chunk, `chunk_index` 0..1212 liền mạch, có `start_line`/`end_line`). Communication và code comments dùng tiếng Việt là OK theo phong cách dự án.

## Nguyên tắc phát triển

**Tra docs trước, code sau.** Trước khi viết bất kỳ thuật toán/logic nào, **bắt buộc web search** tài liệu chính thức của thư viện liên quan để nắm đủ API hiện có. Không được giả định thư viện chỉ làm được những gì mình đã thấy trong code — thư viện thường có nhiều tính năng hơn. Ví dụ: Chonkie không chỉ có `RecursiveChunker` mà còn có nhiều chunker, tokenizer, pipeline utilities khác.

**Ưu tiên thư viện sẵn có, không code tay lại từ đầu.** Sau khi đã tra docs, kiểm tra xem các thư viện đã có trong stack có làm được không:

- **Chunking**: dùng `Chonkie` (`RecursiveChunker`, `RecursiveRules`, `min_characters_per_chunk`). Không tự code greedy merge, sliding window, hay sentence splitter.
- **Orchestration / agentic flow**: dùng `LangGraph` (`StateGraph`, `Send`, `Command`). Không tự code state machine hay retry loop.
- **Retrieval / vector search**: dùng `Qdrant` client trực tiếp. Không tự implement ANN hay re-ranking từ đầu.
- **Graph queries**: dùng `Neo4j` driver + Cypher. Không tự implement graph traversal.
- **HTTP async**: dùng `httpx`. Không dùng `requests` trong async context.
- **Schema validation**: dùng `Pydantic`. Không tự viết dict validation.
- **Postgres**: dùng `psycopg` trực tiếp (xem pattern `chunk_store.py`). Lưu ý strip `+psycopg` khỏi `DATABASE_URL`.

Nếu thư viện hiện có không đủ → ghi rõ lý do trước khi viết custom code. "Tôi không nhớ API" không phải lý do — đọc docs hoặc hỏi.

> **Lưu ý LightRAG**: đã từng dùng `lightrag-hku` nhưng **đã gỡ HOÀN TOÀN** (impedance mismatch). GraphRAG hiện là pipeline DIY tự ráp (xem dưới). **Đừng đề xuất lại LightRAG.** Lý do đầy đủ: `docs/plan/chunking-embedding-plan.md`.

> **Bảng backend tự quản có thể tạo lại tùy ý lúc dev** (`users`/`conversations`/`messages`/`documents`) — sửa thẳng `CREATE TABLE` trong `db.py` rồi drop+tạo lại, **KHÔNG cần viết `ALTER TABLE` migration** lằng nhằng, miễn là chưa có data thật cần giữ (hiện chỉ 2 user seed demo). **TUYỆT ĐỐI KHÔNG** áp dụng cách này cho bảng/store tốn thời gian + tiền API để dựng lại (`rag_chunks`, `timeline_events`, Qdrant collection `history_vn_chunks`, Neo4j graph — dữ liệu index từ LLM calls thật) — mấy cái đó phải giữ nguyên/migrate cẩn thận, không được drop/tạo lại tùy tiện.

## Repository Status

Repo là **git repository** (branch `main`). Không còn ở scaffold stage:

- **`agent-service`**: đã có pipeline indexing thực (preprocessing → chunking → graph extraction → timeline extraction → geocoding) **và** answer flow online — `api/ask.py` (FastAPI `/ask`) + `orchestrator/` (LangGraph: build_query → retrieve → synthesize → validate → visualization, stream SSE). Đây là nơi tập trung gần như toàn bộ logic LLM/retrieval.
- **`backend`**: đã build API gateway (auth JWT, conversation/message, `/ask` streaming proxy, admin documents mock) — xem layout dưới. Module 4 (admin nâng cao) **3/4 nhóm đã code xong** (Hội thoại & chất lượng, Người dùng & quota, Chi phí) + KB Inspector (Module 5) + debug streaming, **cộng thêm 2 hạng mục mới từ `admin-restructure-plan.md`**: **token theo hội thoại/message** (song song chất lượng, không thay thế) và **quản lý Prompt đầy đủ** (sửa/version/promote, agent đọc production lúc chạy + fallback code) — xem `### Admin nâng cao` dưới. Chỉ còn **Cấu hình hệ thống** (retrieval mode mặc định + tinh chỉnh, `system-config-plan.md`) là CHƯA code. **`frontend`**: đã build thật (Vite+React+TS) phủ cả 2 role — auth/chat streaming SSE/multi-turn sidebar/debug panel admin/map+timeline/quản lý tài liệu/KB Inspector/Module 4 (logs+token+users+cost+prompts). Nav admin là **sidebar dọc theo nhóm** (không còn tab ngang). Chỉ mục Cấu hình hệ thống là stub "Sắp cập nhật". Xem `### Frontend layout` dưới + `docs/plan/frontend-plan.md` + `docs/plan/admin-restructure-plan.md` (nav dọc + token + prompt, đã code xong cả 3 hạng mục).

`requirements.txt`, `docker-compose.yml` đã cấu hình. Khi commit, dùng tiếng Việt theo phong cách lịch sử commit hiện có.

## Architecture (3-service split)

Hệ thống tách thành **3 service độc lập** chạy chung trong `infra/compose/docker-compose.yml`:

```
Frontend (Vite/React/TS, :5173)
        ↓ HTTP
Backend / API gateway (FastAPI, :8000)  ← xử lý auth, quản lý docs, gọi agent
        ↓ HTTP (httpx)
Agent-service (FastAPI + LangGraph, :9000)  ← orchestrate RAG + GraphRAG + hybrid
        ↓
   Qdrant (:6333) + Neo4j (:7687) + Redis (:6379) + Postgres (:5432)
```

**Nguyên tắc quan trọng**: backend KHÔNG trực tiếp là agent. Backend chỉ là API gateway gọi sang `agent-service` qua HTTP client (`apps/backend/app/services/agent_client.py`). Mọi logic LLM/retrieval nằm trong `agent-service`.

> **⚠️ TODO trước khi deploy thật (chưa làm) — chưa có auth giữa 2 service**: cả 2 chiều gọi
> HTTP nội bộ hiện **KHÔNG có auth** (không JWT, không API key, không shared secret) —
> `backend → agent-service` (`agent_client.py` gọi `POST /ask`) VÀ `agent-service → backend`
> (`core/runtime_config.py` gọi `GET /internal/config`, xem `system-config-plan.md`) đều dựa
> hoàn toàn vào giả định "2 service chạy cùng máy/cùng mạng riêng tư" — hiện đúng vì đang chạy
> local (`localhost:8000` ↔ `localhost:9000`). Giả định này **SẼ VỠ ngay khi deploy ra khỏi
> localhost** (lên server thật, expose port ra ngoài, tách host, hay cho người ngoài test/dùng
> thử) — ai gọi được port đó cũng đọc/kích hoạt được các endpoint nội bộ này (kể cả `/ask` lẫn
> `/internal/config`). **TRƯỚC KHI deploy ra ngoài máy dev** (kể cả chỉ để demo/cho người
> ngoài test), cần thêm 1 lớp bảo vệ tối thiểu — ví dụ shared-secret header (`X-Internal-Key`
> so khớp giá trị trong `.env`) cho mọi route nội bộ, hoặc cô lập mạng (docker network riêng,
> không map port service nội bộ ra ngoài host/internet). **CHƯA làm** — ghi chú lại để không
> quên khi tới lúc deploy, đừng để lộ khi đã public.

### Hạ tầng đã chạy sẵn (KHÔNG cần docker compose up)
Neo4j + Qdrant + Redis + Postgres **đã cài và chạy sẵn trên remote dev server** qua Docker. URL + credentials đã có trong **root `.env`**. **KHÔNG cần** cài đặt, tải, hay `docker compose up` gì nữa — cứ đọc config từ `.env` mà dùng. Hai bẫy đã xử lý sẵn:
- **Qdrant**: remote chạy HTTP thuần nhưng có API key → client mặc định `https=True` và vỡ SSL. Đã ép `https=False` trong `app/core/qdrant.py`. Point id = `uuid5(NS, chunk_id)`.
- **Postgres**: `DATABASE_URL` dạng `postgresql+psycopg://...` (dialect SQLAlchemy); `psycopg.connect` cần strip `+psycopg`. Đã làm trong `chunk_store.py::_database_url`.

### Storage roles
- **Postgres**: source-of-truth cho mọi dữ liệu index hiện tại:
  - `rag_chunks` — text + metadata mỗi chunk (khóa `chunk_id`)
  - `timeline_events` — atomic event (when–where–what) cho timeline/map (xem dưới)
  - `gazetteer` — địa danh → lat/lon (geocoding; xem dưới)
  - (tương lai) users, documents metadata, conversation logs
- **Qdrant** (collection `history_vn_chunks`): vector embeddings cho RAG truyền thống. Payload = đúng 6 field `CHUNK_VECTOR_META_FIELDS`, **KHÔNG có text**.
- **Neo4j** (+ APOC): knowledge graph cho GraphRAG. Label `:Entity` (key `name` canonical, UNIQUE), rel type `:REL` (prop `keyword`). MERGE idempotent, tích lũy `source_chunk_ids` + `descriptions` xuyên chunk.
- **Redis**: cache + lightweight queue.

**Khóa nối DUY NHẤT giữa các store là `chunk_id`** (Postgres PK ↔ Qdrant payload ↔ Neo4j `source_chunk_ids` ↔ `timeline_events.source_chunk_ids`).

> **Định hướng tương lai (chưa code, mới chốt hướng đi 2026-07-08)**: hiện agent-service tự
> mở kết nối `psycopg` trực tiếp tới Postgres cho mọi module (`tools/graph_rag/chunk_store.py`
> → `rag_chunks`, `tools/visualization/event_store.py` → `timeline_events`,
> `tools/visualization/gazetteer_store.py` → `gazetteer`, `tools/prompts/prompt_store.py` →
> `managed_prompts`/`prompt_versions`, `core/usage_log.py` → `llm_usage`) — pattern này **giữ
> nguyên, KHÔNG đổi cho các module đã code**. Module Postgres MỚI đầu tiên
> (`system_config`, xem `docs/plan/system-config-plan.md`) đi theo hướng khác theo quyết định
> user: agent-service **KHÔNG** tự query bảng đó — gọi qua endpoint nội bộ
> `GET /internal/config` của backend. Đây là điểm khởi đầu cho định hướng đồng bộ hoá về sau:
> khi có dịp, cân nhắc chuyển dần các module kể trên sang cùng pattern (backend sở hữu
> DDL + đọc/ghi, agent-service gọi API thay vì `psycopg` trực tiếp). **CHƯA có plan/lịch
> trình cụ thể cho việc này** — chỉ là định hướng đã chốt, làm khi nào tới lượt, đừng tự ý bắt
> đầu refactor nếu chưa có plan riêng được duyệt.

### GraphRAG — pipeline DIY (offline indexing)
`scripts/run_graph_index.py`: đọc `dataset/chunks_llm.json` → Postgres `rag_chunks` (source of truth) → embed + upsert Qdrant → trích entity/quan hệ (song song) → cache `dataset/graph_extractions.json` → merge Neo4j. Flags: `--limit --workers --overwrite --remerge --skip-vectors --skip-graph`.

**Hai pass trích tách biệt:**
1. **Metadata** (`app/indexing/metadata/`): times/actors/locations/events dạng surface form, cho Qdrant payload + rerank.
2. **Graph** (`app/indexing/graph/entity_relation_extractor.py`): entity-có-kiểu + quan hệ, OpenAI Structured Outputs, schema `app/schemas/graph.py`, prompt `app/prompts/graph_extract.py` (few-shot từ `prompts/entity_type/history_vn.yml`). Có `app/indexing/graph/alias.py` + `normalize.py` cho **alias resolution** (xem Domain notes).

### Timeline + Map data layer (offline indexing → builder online)
Lớp dữ liệu mới song song, dựng **offline 1 lần**; lúc trả lời chỉ **lọc & ráp online** (không trích lại). **Source-of-truth của hạng mục này: `docs/plan/timeline-map-plan.md`** — cập nhật file đó khi đổi quyết định.

Pipeline offline 3 bước rời (verify từng bước):
1. `scripts/run_segmentation.py` — segmenter gom heading thành "unit" (cap 50K ký tự) → `dataset/timeline_units.json`.
2. `scripts/run_timeline_index.py` — extract LLM mỗi unit → atomic event (cache `dataset/timeline_extractions.json`, resume theo `unit_id`+version) → reconcile (dedup + `event_id` tất định `uuid5`) → load Postgres `timeline_events`.
3. `scripts/build_gazetteer.py` — geocode `timeline_events.locations` (Google trước → LLM fallback) → Postgres `gazetteer`. **⚠️ TẠM HOÃN** (xem dưới).

Online: `app/tools/visualization/builder.py::build_visualization(retrieved_chunk_ids)` → `select_events_by_chunks` (toán tử mảng giao `&&`) → join `gazetteer` lấy lat/lon → trả `VisualizationPayload` (map markers + timeline items, link 2 chiều bằng `event_id`), honest fallback (thiếu nơi → chỉ timeline; thiếu time → chỉ map).

> **⚠️ Khâu toạ độ (gazetteer + lat/lon) đang TẠM HOÃN — làm CUỐI** (quyết định user 2026-06-22). Lý do: độ chính xác địa điểm quan trọng + cần review kĩ (điểm yếu: địa danh trùng tên khác tỉnh bị provider chấm "cao" nhưng sai). **Tạm KHÔNG chạy `build_gazetteer.py`** (cả Google lẫn LLM). KHÔNG cần sửa/disable code: pipeline timeline (`run_timeline_index.py`) không phụ thuộc `app/indexing/geocoding/`, vẫn cho time + `locations` (tên). Builder gặp `gazetteer` rỗng → fallback chỉ-timeline, không vỡ. Nếu thấy `gazetteer` rỗng/dở dang: đó là CỐ Ý.

### Agent-service internal layout (`apps/agent-service/app/`)
- `indexing/preprocessing/` — chuẩn hóa text (cleaner.py). Idempotent + non-destructive.
- `indexing/` (root) — `heading_parser.py`, `llm_chunker.py`, `chunk_slicer.py`, `token_counter.py`.
- `indexing/metadata/` — pass trích metadata surface form cho chunk.
- `indexing/graph/` — pass trích entity/quan hệ + alias resolution.
- `indexing/timeline/` — `segmenter.py`, `atomic_event_extractor.py`, `reconcile.py`.
- `indexing/geocoding/` — `geocoder.py` (Google + LLM hybrid).
- `tools/graph_rag/` — `chunk_store.py` (Postgres), `vector_store.py` (Qdrant), `graph_store.py` (Neo4j, + `list_entities`/`get_entity` cho KB Inspector).
- `tools/visualization/` — `event_store.py` (`timeline_events`), `gazetteer_store.py` (`gazetteer`), `builder.py` (online).
- `tools/prompts/` — `prompt_store.py`: bảng `managed_prompts`/`prompt_versions` (lazy tạo, mirror chunk_store), `get_active_prompt(key, fallback)` đọc version `production` (cache TTL 60s, **luôn fallback về hằng code** nếu DB thiếu/lỗi, nuốt mọi exception — dùng cho 3 prompt ONLINE/GUARDRAIL). Seed từ `scripts/seed_prompts.py`.
- `prompts/` — hằng `SYSTEM_PROMPT` trong code (nguồn seed + fallback runtime), có versioning theo comment (graph_extract, metadata_extract, timeline_extract, geocode, alias_judge, build_query, synthesize, guardrails_input).
- `schemas/` — Pydantic models (chunk, graph, metadata, timeline, gazetteer, visualization, alias, `ask.py` request/response — có `conversation_id`/`message_id` để quy `llm_usage`, `kb.py` cho KB Inspector).
- `core/` — config, llm, embedding, clients (qdrant, neo4j), `usage_log.py` (`record_usage` → bảng `llm_usage` gồm `conversation_id`/`message_id`, tạo lazy + `ALTER ... IF NOT EXISTS` idempotent, nuốt mọi exception).
- `scripts/` — CLI utilities (xem Commands) + `seed_prompts.py` (seed 8 managed prompt từ hằng code, idempotent).
- `api/` — `ask.py` (`POST /ask`, streaming SSE), `kb.py` (`GET /kb/entities`, `/kb/entities/{norm_name}` — read-only, phục vụ backend proxy Module 5).
- `orchestrator/` — LangGraph: `nodes.py` (build_query → retrieve → synthesize → validate → visualization, ghi `llm_usage` kèm conversation_id/message_id, dùng `get_active_prompt` cho build_query/synthesize), `guardrails.py` (`check_input` dùng `get_active_prompt("guardrails_input", ...)`), `runner.py` (`run_ask_stream`, emit event `debug` trước `done`), `state.py`, `synthesis.py`.
- `tools/traditional_rag/`, `tools/hybrid/` — `retriever.py` mỗi thư mục; node `retrieve()` gọi thẳng `tools/hybrid/retriever.py::retrieve_hybrid`, set `retrieval_mode="hybrid"`.

### Backend internal layout (`apps/backend/app/`)
Cấu trúc theo lớp (KHÔNG dùng `modules/` như scaffold cũ; KHÔNG ORM/Alembic — psycopg
tay + `CREATE TABLE IF NOT EXISTS`). Plan: `docs/plan/backend-plan.md`.
- `core/` — `config.py` (pydantic-settings đọc root `.env`), `db.py` (psycopg + DDL 4
  bảng + `connection()`/`init_schema()`), `security.py` (bcrypt + PyJWT), `errors.py`
  (`AppError` → body `{code,message}`).
- `models/` — data access psycopg trực tiếp: `user.py` (+ `is_active`/`question_quota`),
  `conversation.py` (conversations + messages + `count_user_messages_today`), `document.py`,
  `inspect.py` (chunks/events cho KB Inspector), `logs.py` (conversation logs admin +
  `list_attributed_usage_rows`/`get_message_token_rows` cho token theo hội thoại),
  `cost.py` (đọc `llm_usage`, tự bắt `UndefinedTable` → `[]`), `prompt.py` (CRUD
  `managed_prompts`/`prompt_versions`: `create_staging_version`, `promote` — 1 transaction,
  demote production cũ → archived + ghi `promoted_by`/`promoted_at`). Mọi hàm SYNC; API layer
  gọi qua `anyio.to_thread`.
- `schemas/` — Pydantic request/response: `auth.py`, `chat.py`, `document.py`, `common.py`,
  `inspect.py`, `logs.py` (+ `TokenSummary`/`MessageTokens`), `user.py`, `cost.py`, `prompt.py`.
- `api/` — router: `health.py` (`/health`,`/ready`), `auth.py` (login/me/logout, check
  `is_active`), `chat.py` (conversation CRUD + `/ask` streaming — truyền `conversation_id`/
  `message_id` sang agent, gác `debug`, check quota), `documents.py` (admin mock),
  `inspect.py` (`/api/admin/kb/*` — chunks/events Postgres trực tiếp + proxy entities sang
  agent-service), `logs.py` (`/api/admin/logs/*` — hội thoại & chất lượng + `token-summary`/
  `conversations/{id}/tokens`), `users.py` (`/api/admin/users*` — CRUD + quota + khóa),
  `cost.py` (`/api/admin/cost/*` — dashboard chi phí), `prompts.py` (`/api/admin/prompts/*`
  — list/detail/version/`versions`(POST tạo staging)/`versions/{no}/promote`, `require_admin`,
  `created_by`/`promoted_by` = email admin), `deps.py` (`get_current_user` — re-check
  `is_active`, `require_admin`, `get_owned_conversation`).
- `services/` — `agent_client.py` (`open_ask_stream` + `user_id`/`conversation_id`/
  `message_id` + error mapping + parse/format SSE), `sse_collector.py` (gom event tái dựng
  message), `conversation_service.py` (derive_title + bounded history), `quality_service.py`
  (`compute_quality_summary`, thuần), `cost_service.py` (`compute_cost_overview/by_day/by_task`,
  thuần), `token_service.py` (`compute_token_summary`/`build_message_tokens`, thuần) — các
  service cuối cùng idiom hàm thuần không I/O để unit-test không cần DB.
- `scripts/` — `init_db.py` (tạo 4 bảng, chạy 1 lần), `seed_users.py` (2 user demo dev).

**Backend chỉ STREAMING**: `/ask` luôn trả `text/event-stream`, proxy nguyên event SSE của
agent-service, gom token lưu `messages`. Lỗi TRƯỚC khi mở stream → HTTP 503/504/502; lỗi
SAU khi mở → event `error`. Bảng: `users/conversations/messages/documents`; `messages.
created_at` dùng `clock_timestamp()` (không `now()`) để thứ tự message ổn định trong 1 txn.

**TTFT** (`messages.ttft_ms`): đo Ở BACKEND, KHÔNG phải agent — bấm giờ đầu handler `ask()`,
chốt ở event `token` ĐẦU TIÊN proxy xuống FE (`api/chat.py::_proxy_stream` → `SseCollector.
mark_first_token`). Vậy con số gồm cả quota check + history + guardrails + build_query +
retrieval + LLM = đúng khoảng người dùng chờ tới chữ đầu tiên, KHÔNG phải TTFT riêng của LLM
(OpenAI không trả metric này; muốn tách riêng phần LLM thì phải đo thêm trong `synthesis.py`).
Đi kèm event `done` (FE hiện ngay) + lưu DB (thấy lại sau reload). NULL = message user, hoặc
stream hỏng/blocked trước token đầu → UI hiện "—", và trung bình/p95 ở
`quality_service::_ttft_stats` bỏ qua row NULL (mẫu số riêng `ttft_measured_count`).

### Admin nâng cao — 3 file plan, KHÔNG trùng nội dung, sửa gì thì sửa đúng file
- `docs/plan/backend-additions-plan.md` — **đã code xong** Phần 1–4: debug streaming, read
  endpoints Module 5 (KB Inspector), 3/4 nhóm Module 4 gốc (logs & chất lượng, users & quota,
  cost dashboard). `users` table đã sửa thẳng `CREATE TABLE` (drop+tạo lại, không migration)
  thêm cột `is_active`/`question_quota`.
- `docs/plan/admin-restructure-plan.md` — **đã code xong CẢ 3 hạng mục** (chốt 2026-07-03,
  điều chỉnh layout 2026-07-05):
  - **Item 1 — Nav dọc**: sidebar admin chuyển từ tab ngang sang **nhóm dọc** (NỘI DUNG / KHO
    TRI THỨC / QUẢN TRỊ), mỗi chức năng 1 route riêng (`/admin/logs`, `/admin/kb/chunks`...).
    Đã xoá `AdminAdvancedPage.tsx`/`AdminKbPage.tsx` (tab gộp) + gỡ điều hướng chéo KB
    (chunk↔entity↔event không còn nhảy tab, mỗi trang tự quản selection).
  - **Item 3 — Token theo hội thoại**: `llm_usage` thêm cột `conversation_id`/`message_id`
    (ALTER idempotent, giữ data cũ). **Bổ sung SONG SONG chất lượng, KHÔNG thay thế** — cả 2
    luôn hiển thị cạnh nhau. KHÔNG quy ra tiền $. Model hiển thị **ở từng dòng task** (không
    phải 1 model chung/message) vì build_query/synthesize và guardrail_input có thể khác model.
  - **Item 2 — Quản lý Prompt**: chỉ 3 prompt **ONLINE/GUARDRAIL** (build_query, synthesize,
    guardrails_input) wiring runtime thật; 5 prompt **INDEXING** (offline) chỉ đăng ký +
    version được, **CHƯA nối vào script indexing** (ghi rõ "chưa nối" ở UI). An toàn: agent
    LUÔN fallback về hằng code nếu DB thiếu/lỗi.
  - Trang Hội thoại (`/admin/logs`) redesign sang **bố cục 3 cột inline** (mượn từ Socratic,
    KHÔNG mượn metric không có như downvote/mastery): trái = danh sách phiên, giữa = replay
    hội thoại, phải = tab Chất lượng/Token cho phiên đang chọn.
- `docs/plan/system-config-plan.md` — nhóm **Cấu hình hệ thống** (14 field tinh chỉnh
  retrieval/synthesize đang hardcode trong `Settings`), tách riêng vì đụng orchestrator đang
  chạy ổn định. **CHƯA code** (vẫn stub "Sắp cập nhật"). **Retrieval mode
  (traditional/graph/hybrid) KHÔNG thuộc phạm vi nhóm này** (chốt 2026-07-07) — mode vẫn
  hardcode mặc định `"hybrid"`, chỉ user tự chọn per-câu-hỏi ngay trong khung chat
  (`Composer.tsx`, đã chạy sẵn từ trước); admin KHÔNG có ô đặt mode mặc định hệ thống (tránh
  phức tạp hoá không cần thiết). KHÔNG quản lý model qua config. **Điểm kiến trúc riêng của
  nhóm này**: agent-service đọc `system_config` qua gọi HTTP `GET /internal/config` của
  backend, KHÔNG tự query Postgres trực tiếp như các module khác — xem `### Storage roles`.

### Frontend layout (`apps/frontend/src/`) — đã build
Vite+React 18+TS. TanStack Query (server state) + Zustand (auth/UI) + Tailwind v3 (tokens:
brand `#A4161A`, nền kem, serif+sans) + Radix + `@vis.gl/react-google-maps` +
`react-force-graph-2d` + `recharts`. Test: Vitest + Testing Library. SSE `/ask` qua
`fetch`+`ReadableStream` tay. Route cứng `/` (user) vs `/admin/*` (RoleGuard admin), nav admin
là **sidebar dọc theo nhóm** (`AppSidebar.tsx`, KHÔNG còn tab ngang).
- `app/` — `App.tsx` (providers + router + boot getMe), `routes.tsx` (route tree, export array;
  mỗi chức năng admin 1 route con riêng — `admin/kb/{chunks,graph,timeline}`,
  `admin/{logs,users,cost,prompts,config}`; lazy trang nặng: `kb/graph` (force-graph), `cost`
  (recharts), `prompts`; redirect back-compat từ path gộp cũ `/admin/kb`, `/admin/advanced`).
- `api/` — `client.ts` (fetch wrapper Bearer + `{code,message}`→ApiError + 401 clear),
  `askStream.ts` (⭐ parser SSE), `auth/chat/documents/kb/logs/users/cost/prompts.ts`.
- `store/` — `authStore` (persist), `chatUiStore` (`selectedEventId` link map↔timeline, debugOpen).
- `features/auth` — RequireAuth/RoleGuard/LoginForm.
- `features/chat` — `chatReducer` (thuần, test) + `useChat` + ChatPanel/MessageList/Bubble/
  Composer/Citation/Clarification/DebugPanel(admin)/VizPanel.
- `features/map` + `features/timeline` — EventMap/EventMarker/MapEmptyState + Timeline/Row,
  honest fallback (gazetteer hoãn → markers rỗng → empty-state).
- `features/admin` — DocumentTable/StatusBadge/DocumentFormModal (CRUD mock).
- `features/kb` — Module 5 inspector: Chunk/Entity/Event Table+Detail, EgoGraph. Mỗi trang
  (Chunks/Graph/Timeline) **độc lập, tự quản selection nội bộ** — KHÔNG còn điều hướng chéo
  qua tab (bỏ theo Item 1 admin-restructure-plan, chunk_id/entity/event chỉ còn text tra cứu).
- `features/advanced` — Module 4: `UsersTab`/`CostTab` + `ConfigTabStub` ("Sắp cập nhật") +
  trang Hội thoại **bố cục 3 cột** (`LogsTab` lắp `ConversationSessionList` trái /
  `ConversationReplay` giữa / `ConversationDetailPanel` phải — 2 tab Chất lượng/Token) +
  `QualitySummaryCard`/`TokenSummaryCard` (2 card tổng đặt cạnh nhau, không thay thế nhau).
- `features/prompts` — Module quản lý Prompt: `PromptTree` (trái, theo nhóm ONLINE/GUARDRAIL/
  INDEXING) / `PromptEditor` (giữa, sửa content+note, lưu staging hoặc đẩy production) /
  `VersionHistory` (phải, badge status + audit `created_by`/`promoted_by` + nút So sánh) +
  `DiffModal` (diff theo dòng, thuật toán LCS thuần ở `diff.ts`, có test).
- `components/` — Modal(Radix)/Spinner/EmptyState/ConfidenceBadge/`PageHeader`(tiêu đề+mô tả
  mỗi trang admin)/`StatCard`(ô số liệu dùng chung cho Quality/Token/Cost) dùng chung;
  `pages/` — mỗi route admin 1 file wrapper mỏng (`AdminDocumentsPage`, `AdminKb{Chunks,Graph,
  Timeline}Page`, `AdminLogsPage`, `AdminUsersPage`, `AdminCostPage`, `AdminPromptsPage`,
  `AdminConfigPage`) bọc component tab tương ứng + `PageHeader`.

**Commands** (từ `apps/frontend`): `npm run dev` (:5173), `npm run typecheck`, `npm run test`,
`npm run build`. `.env`: `VITE_API_BASE_URL`, `VITE_GOOGLE_MAPS_API_KEY`.

### Visualization contract (quan trọng)
Map và timeline phải dùng **chung `event_id`** để liên kết hai chiều (click marker → highlight timeline item và ngược lại). Đã hiện thực trong `builder.py`. Quy tắc:
- Event thiếu địa điểm → chỉ hiển thị timeline
- Event thiếu thời gian → chỉ hiển thị map
- Không đủ data → KHÔNG ép sinh marker; honest về uncertainty
- Visualization data sinh ra **online từ events đã retrieve**, KHÔNG pre-compute theo câu hỏi. Metadata (time/location/lat/lon/confidence) phải được extract **offline** khi indexing document.
- Marker confidence = YẾU NHẤT giữa confidence của event và của toạ độ; render đậm/nhạt theo đó.

## Commands

> Hạ tầng (Qdrant/Neo4j/Redis/Postgres) đã chạy remote — **KHÔNG cần `docker compose up`** cho dev thường ngày, cứ đọc root `.env`.

### Lint / typecheck / test (Python services)
**KHÔNG có venv ở root repo.** Mỗi app tự có venv riêng: `apps/agent-service/venv/` và
`apps/backend/venv/`. Chạy từ đúng thư mục app (hoặc set `PYTHONPATH` nếu chạy file ngoài):
```powershell
cd apps/agent-service
.\venv\Scripts\python.exe -m pytest tests                # toàn bộ (192 test, hermetic — không chạm DB)
.\venv\Scripts\python.exe -m pytest tests/test_foo.py::test_bar  # 1 test
$env:MYPYPATH="."
.\venv\Scripts\python.exe -m mypy --explicit-package-bases app   # thiếu flag này -> lỗi
                                                                   # "Source file found twice"
                                                                   # (app/core/config.py); ruff.exe
                                                                   # có thể bị Windows App Control
                                                                   # chặn tuỳ máy (WinError 4551)
```

### Backend (API gateway, :8000)
Venv riêng `apps/backend/venv/`. Lần đầu: tạo bảng + seed user demo. Test backend dùng
Postgres remote thật (cô lập bằng transaction rollback, **cần DB tới được** — nếu không sẽ
timeout ở fixture `_ensure_schema` autouse); agent-service được mock qua `httpx.MockTransport`,
không cần agent chạy. `test_inspect.py` cần bảng `rag_chunks`/`timeline_events` đã index sẵn
— DB mới trống sẽ fail 7 test đó (không phải lỗi code, chỉ thiếu data).
```powershell
$env:PYTHONIOENCODING="utf-8"
cd apps/backend
.\venv\Scripts\python.exe scripts/init_db.py        # CREATE TABLE IF NOT EXISTS 4 bảng (idempotent)
.\venv\Scripts\python.exe scripts/seed_users.py     # admin@example.com/admin123, teacher@example.com/teacher123 (dev)
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000   # chạy server
.\venv\Scripts\python.exe -m pytest tests                       # 116 test
```

### Tiền xử lý dataset (preprocessing)
Chuẩn hóa heading, dash (–/—→-), smart quote (“”→”), ellipsis (…→...), gộp blank line, strip **soft hyphen U+00AD** (di chứng copy từ PDF/DOCX, phá tokenization). **KHÔNG** tách paragraph dài (chunking xử lý qua Level 4 fallback). Idempotent + non-destructive → trả `PreprocessReport`.
```powershell
$env:PYTHONIOENCODING="utf-8"   # in được tiếng Việt trên Windows
cd apps/agent-service
python scripts/preprocess_dataset.py --input ../../lichsu.md --output ../../lichsu.clean.md
```

### Chunking experiment
`test.py` (nếu có) ở root so sánh `RecursiveChunker` vs `SlumberChunker` (Chonkie). LLM chunking thật: `scripts/run_llm_chunking.py` → `dataset/chunks_llm.json`.

### Indexing chính (offline, tốn API cost — cân nhắc trước khi re-run)
```powershell
# GraphRAG: chunks_llm.json → rag_chunks (Postgres) → Qdrant → graph (Neo4j)
python scripts/run_graph_index.py --limit -1 --workers 8

# Timeline 3 bước (verify từng bước):
python scripts/run_segmentation.py                  # → dataset/timeline_units.json
python scripts/run_timeline_index.py --limit -1     # → timeline_events (Postgres)
# python scripts/build_gazetteer.py                 # ⚠️ TẠM HOÃN — đừng chạy

# Alias resolution cho KG
python scripts/build_alias_map.py

# Reset stores (drop/recreate) khi cần
python scripts/reset_stores.py
```
`run_graph_index.py` flags: `--limit --workers --overwrite --remerge --skip-vectors --skip-graph`.
`run_timeline_index.py` flags: `--limit --skip-reconcile --skip-db --allow-empty` (`--limit -1` = chỉ reconcile + nạp DB từ cache). **Guard**: reconcile ra 0 event → KHÔNG nạp (tránh TRUNCATE xoá trắng bảng), trừ khi `--allow-empty`.

### Map POC
Render map = **Google Maps JavaScript API** (AdvancedMarkerElement), dùng `GOOGLE_MAPS_API_KEY`. POC: `google_map_test.py` (root) + `scripts/show_google_map.py`. *(`trackasia-map-test.html` cũ chỉ còn làm tham khảo — đã chuyển hẳn sang Google.)*

## Configuration

`.env` ở root là **nguồn cấu hình DUY NHẤT** cho monorepo; `app/core/config.py` trỏ tuyệt đối tới file đó. Mỗi app cũng có `.env.example` riêng cho local dev.

Giá trị **thực tế** trong code (đừng tin mù `.env.example`, có chỗ còn placeholder cũ):
- **Embedding + tokenizer**: model tiếng Việt `AITeamVN/Vietnamese_Embedding` (KHÔNG phải OpenAI `text-embedding-3-small` như `.env.example` để). Field: `embedding_model`, `embedding_tokenizer`.
- **LLM default**: `llm_model = "gpt-5.4-nano"` (qua gateway OpenAI-compatible, set `OPENAI_BASE_URL`). Knob riêng: `graph_llm_model`, `timeline_llm_model` (None = fallback `llm_model`; đặt model hỗ trợ Structured Outputs strict).
- **Geocoding**: `google_maps_api_key` (rỗng → bỏ qua Google, chỉ LLM fallback). ⚠️ ToS Google: cache lat/lon ≤ 30 ngày — xem `docs/reference/google-maps-api.md`.
- **Chunking**: `chunk_size=700`, `min_characters_per_chunk=80`.
- **Storage**: `neo4j_uri/user/password`, `qdrant_host/port/api_key`, `qdrant_collection=history_vn_chunks`, `redis_url`, `database_url`.

## Domain-specific notes (lịch sử Việt Nam)

Đây là phần đặc thù domain mà code generic không cover:

- **Alias resolution**: "Nguyễn Tất Thành / Nguyễn Ái Quốc / Hồ Chí Minh / Bác Hồ" là cùng 1 entity. Đã hiện thực trong `app/indexing/graph/alias.py` + `normalize.py` + `build_alias_map.py`. Là một điểm contribution của đồ án.
- **Temporal anchor inheritance**: Document có cấu trúc "Năm 1859, ... [đoạn]. Đầu năm 1861, ... [đoạn]". Các câu giữa các anchor inherit time/location từ anchor đầu segment. Timeline extractor hạ `confidence` khi suy năm từ ngữ cảnh.
- **Confidence + provenance**: Mỗi event lưu time/location lẫn `confidence` (`cao`/`vừa`/`thấp`, đồng bộ `AliasVerdict`) và provenance qua `source_chunk_ids`. Marker render khác nhau theo confidence (đậm = explicit, nhạt = inferred).
- **Honest behavior**: Khi không đủ data → trả lời "chưa đủ thông tin" / không sinh marker, thay vì hallucinate. Quan trọng vì fact sai trong lịch sử bị trừ điểm nặng.
- **Địa danh nước ngoài**: corpus có Paris/Genève/Trung Quốc/đảo Réunion... → geocoding `region=vn` chỉ BIAS, KHÔNG ép chỉ-Việt-Nam.

## Reference assets

- `lichsu.clean.md` — corpus chính đã preprocess (~3.1MB, 7.623 dòng; 3 h1, 33 h2, 75 h3, 106 h4...). `lichsu.md` là bản gốc. Không index lại nhiều lần (tốn API cost).
- `dataset/chunks_llm.json` — 1213 chunk (`source_file=lichsu.clean.md`, có `start_line`/`end_line`).
- `dataset/*.json|*.md` — cache + review của các pipeline: `graph_extractions.json`, `alias_map.json`/`alias_review.md`, `timeline_units.json`, `timeline_extractions.json`, `gazetteer.json`/`gazetteer_review.md`, `entities_by_type.md`.
- `README.md` — đặc tả chức năng đầy đủ (admin, teacher, RAG, GraphRAG, hybrid, map, timeline, MVP scope). Nguồn truth cho scope.
- `docs/plan/` — plan đã duyệt: `chunking-embedding-plan.md` (lý do gỡ LightRAG + DIY pipeline), `llm-chunking-plan.md`, `timeline-map-plan.md` (source-of-truth timeline/map), `lichsu-headings.md`, `backend-plan.md` (kiến trúc backend gốc), `frontend-plan.md` (kế hoạch frontend đầy đủ 2 role), `backend-additions-plan.md` (Module 4 build ngay + KB Inspector + debug streaming), `admin-restructure-plan.md` (nav dọc + token theo hội thoại + quản lý Prompt — **đã code xong cả 3**, xem `### Admin nâng cao` ở trên), `system-config-plan.md` (Cấu hình hệ thống — retrieval mode + tinh chỉnh, tách riêng vì rủi ro cao, CHƯA code).
- `docs/reference/google-maps-api.md` — tham chiếu Google Geocoding/Maps + ToS caching.
- `docs/design/frontend-scope.md`, `docs/brainstorming/` — scope frontend + session notes kiến trúc.
