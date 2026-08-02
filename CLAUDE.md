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
- **`backend`**: đã build API gateway (auth JWT, conversation/message, `/ask` streaming proxy, admin documents — **hết mock**, danh mục nối kho tri thức thật, xem `### Tài liệu (Module 3)`) — xem layout dưới. Module 4 (admin nâng cao) **3/4 nhóm đã code xong** (Hội thoại & chất lượng, Người dùng & quota, Chi phí) + KB Inspector (Module 5) + debug streaming, **cộng thêm 2 hạng mục mới từ `admin-restructure-plan.md`**: **token theo hội thoại/message** (song song chất lượng, không thay thế) và **quản lý Prompt đầy đủ** (sửa/version/promote, agent đọc production lúc chạy + fallback code) — xem `### Admin nâng cao` dưới. Chỉ còn **Cấu hình hệ thống** (retrieval mode mặc định + tinh chỉnh, `system-config-plan.md`) là CHƯA code. **`frontend`**: đã build thật (Vite+React+TS) phủ cả 2 role — auth/chat streaming SSE/multi-turn sidebar/panel tiến trình 2 tầng (tầng 2 admin, thay DebugPanel đã xoá — xem `### Panel tiến trình 2 tầng`)/map+timeline/quản lý tài liệu/KB Inspector/Module 4 (logs+token+users+cost+prompts). Nav admin là **sidebar dọc theo nhóm** (không còn tab ngang). Chỉ mục Cấu hình hệ thống là stub "Sắp cập nhật". Xem `### Frontend layout` dưới + `docs/plan/frontend-plan.md` + `docs/plan/admin-restructure-plan.md` (nav dọc + token + prompt, đã code xong cả 3 hạng mục).

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

### Cổng vào hệ thống — đăng ký công khai + đăng nhập Google (xong 2026-07-30)
Plan: `docs/plan/auth-landing-plan.md`. **Landing page + đổi cây route `/` → `/chat` (pha B)
HOÃN theo yêu cầu user** — `/` vẫn là `AskPage` sau `RequireAuth`; `/login` + `/register` là 2
route công khai duy nhất.

- **`POST /api/auth/register`** — mở, không admin duyệt: `role` **hardcode `"user"`** trong
  handler (`RegisterRequest` KHÔNG có field role), trả `LoginResponse` 201 → auto-login.
  Trùng email → `409 email_taken`.
- **Chuẩn hoá email đặt ở TẦNG REPO** (`models/user.py::normalize_email`, gọi trong
  `get_user_by_email` + `create_user`), KHÔNG ở handler: có 4 cửa cùng chạm email, sót một cửa
  là tài khoản nhân đôi (`TEXT UNIQUE` so byte). Tiện thể sửa bug `/login` cũ tra email
  nguyên văn. Chỉ `strip().lower()` — CỐ Ý không bỏ dấu chấm/`+tag` (luật riêng Gmail).
- **Mật khẩu đếm BYTE, không đếm ký tự**: `security.validate_bcrypt_password` (≤72 byte) gọi
  ở `RegisterRequest` + `UserCreate` (cửa admin) + `hash_password`. `hash_password` KHÔNG còn
  cắt im lặng; `verify_password` **vẫn cắt** (hash cũ sinh từ bản đã cắt — bỏ cắt là khoá cửa
  chính những tài khoản đó).
- **`POST /api/auth/google`** — luồng **ID token** (không client secret / redirect URI /
  PKCE). `users` thêm `google_sub TEXT UNIQUE` + `password_hash` nullable (2 ALTER idempotent).
  **KHÔNG tự ghép Google vào tài khoản mật khẩu cùng email** → `409 account_link_required`
  (`email_verified` chỉ chứng minh Google tin email, không chứng minh cùng người → lỗ hổng
  pre-hijacking). Thứ tự `except` **không được đảo**: `TransportError` (subclass của
  `GoogleAuthError`) → `503`, rồi `(ValueError, GoogleAuthError)` → `401`.
  `GOOGLE_CLIENT_ID` rỗng → `503 google_login_disabled`; frontend không render nút.
- **Sửa bug `client.ts` đang chạy**: 401 chỉ coi là "hết phiên" khi request **có token** và
  **không phải** `/api/auth/{login,register,google}` — trước đó gõ sai mật khẩu hiện "Phiên
  đăng nhập đã hết hạn". `state.from` của `RequireAuth` nay **được đọc** qua
  `features/auth/redirectTarget.ts` (mặc định `"/"`; đổi hằng đó khi làm pha B).
- ⏳ **Còn nợ**: Google Cloud Console (plan §4.3.1, user tự bấm) · landing page · rate limit
  (plan §6b, làm trước khi mở ra ngoài localhost) · liên kết Google vào tài khoản có sẵn (cần
  trang cá nhân).

### Auth nội bộ giữa 2 service — shared secret `X-Internal-Key` (xong 2026-07-30)
Cả 2 chiều gọi HTTP nội bộ **đã có auth**, dùng shared secret `INTERNAL_API_KEY` (root `.env`)
qua header `X-Internal-Key`. Trước đây cả 2 chiều đều trần, chỉ dựa vào giả định "2 service
cùng máy" — giả định đó vỡ ngay khi `--host 0.0.0.0` hoặc deploy.

- **Module đối xứng, 2 file cùng tên khác vai**: `agent-service/app/core/internal_auth.py` gác
  `/ask` + `/kb/*` và **gửi** key khi `runtime_config.py` gọi `GET /internal/config`;
  `backend/app/core/internal_auth.py` gác `/internal/*` và **gửi** key từ `agent_client.py`.
  Mỗi file có `verify_internal_key` (dependency) + `internal_headers()` (bên gửi).
- **Dùng `APIKeyHeader`** (không tự đọc `Request.headers`) → scheme vào OpenAPI → Swagger
  `:9000/docs` có nút **Authorize**, dán key 1 lần là test được. Gác ở **cấp router**, không
  phải cấp app.
- **CỐ Ý KHÔNG dùng JWT ở tầng này**: JWT trả lời "user nào" và nằm trong tay user
  (localStorage) → user tự gọi thẳng `:9000` được, đi vòng qua quota + `debug=False` + log ở
  backend. Key này trả lời "service nào". Test `test_internal_config_rejects_user_jwt` chốt
  điều đó: JWT admin **không** mở được `/internal/*`.
- **Fail-closed, KHÔNG có nhánh "key rỗng thì bỏ qua"**: thiếu/sai key → 401; server chưa
  cấu hình key → 500 `internal_key_not_configured`. Cả 2 `/ready` (backend + agent) đưa
  `internal_api_key` vào checks để thiếu key lộ lúc deploy, không đợi câu hỏi đầu tiên.
- **`/health` + `/ready` của agent-service TÁCH sang `api/health.py` và để PUBLIC** — gác cả
  router `ask` thì backend `api/health.py::_ping_agent` (gọi `/ready` không mang header) sẽ
  báo `agent_service: false` vĩnh viễn, nhìn như agent sập.

> **⚠️ Còn lại trước khi deploy thật**: (1) `BACKEND_SECRET_KEY` trong `.env` vẫn là
> placeholder `generate_some_secure_hex_key_here` → ai đọc `.env.example` cũng ký được JWT
> `role=admin`; check `secret_key` trong backend `/ready` so với hằng KHÁC
> (`change-me-to-a-long-random-string`) nên đang báo xanh sai. (2) `infra/compose/
> docker-compose.yml` map **mọi** port ra host (`9000`, `5432`, `7474/7687`, `6333`, `6379`)
> + bind-mount source → là compose DEV, KHÔNG dùng cho production; production cần bản chỉ
> map port backend. Shared secret ở trên là lớp thứ 2 (defense in depth), KHÔNG thay thế việc
> cô lập mạng. **(3) Rate limit — HOÃN có chủ ý (quyết định user 2026-07-30)**: `/login` hiện
> **không giới hạn số lần thử** (mời brute-force) và quota chỉ tính **theo tài khoản**
> ([db.py](apps/backend/app/core/db.py) `question_quota`) nên khi mở đăng ký công khai, ai
> muốn vượt quota chỉ cần tạo thêm tài khoản. Chấp nhận được khi chạy localhost để demo;
> **phải làm trước khi mở ra internet**. Thiết kế + 4 mức đã soạn sẵn ở
> `docs/plan/auth-landing-plan.md` §6b, chỉ việc code.

### Role: `admin` | `user` (đổi tên từ `teacher`, 2026-07-30)
Hệ thống có đúng **2 role**: `admin` và `user`. Role người dùng thường trước đây tên
`teacher`, đã đổi thành `user` toàn hệ thống (`Role` literal ở BE + FE, seed, 18 file test).
Chi tiết + lý do: `docs/plan/auth-landing-plan.md` §0.
- **KHÔNG có migration/backfill nào trong code** — thay vì `UPDATE role`, đã **xoá thẳng tài
  khoản demo cũ** `teacher@example.com` (kéo theo 13 hội thoại/50 message/220 activity của
  riêng nó, quyết định user 2026-07-30 vì dev data tạo lại được) rồi seed lại
  `user@example.com`. Dữ liệu của `admin@example.com` giữ nguyên.
- **Các plan doc CŨ vẫn viết "teacher"** (`backend-plan.md`, `frontend-plan.md`,
  `citation-viewer-plan.md`, `backend-additions-plan.md`, `system-config-plan.md`) — giữ
  nguyên làm bản ghi lịch sử, đọc là role `user` hiện nay. (`README.md` +
  `docs/design/frontend-scope.md` đã đổi vì là doc scope đang sống.)

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
1. `scripts/run_segmentation.py` — segmenter gom heading thành "unit" (cap **30K** ký tự, **không overlap**, unit giữ nguyên từng chunk) → `dataset/timeline_units.json`. Chốt chặn: mỗi chunk phải nằm ĐÚNG MỘT unit, vỡ → không ghi artifact, thoát mã 1.
2. `scripts/run_timeline_index.py` — extract LLM **1 request/unit**, LLM trả `chunk_results` theo marker `ref` → cache `dataset/timeline_extractions.json` **khoá theo `chunk_id`** (resume: unit xong khi MỌI chunk của nó khớp `prompt_version`+`unit_id`) → reconcile (dedup + `event_id` tất định `uuid5`) → load Postgres `timeline_events`. Xem `### Timeline extract theo unit` dưới.
3. `scripts/build_gazetteer.py` — geocode `timeline_events.locations` (Google trước → LLM fallback) → Postgres `gazetteer`. **⚠️ TẠM HOÃN** (xem dưới).

Online: `app/tools/visualization/builder.py::build_visualization(retrieved_chunk_ids)` → `select_events_by_chunks` (toán tử mảng giao `&&`) → join `gazetteer` lấy lat/lon → trả `VisualizationPayload` (map markers + timeline items, link 2 chiều bằng `event_id`), honest fallback (thiếu nơi → chỉ timeline; thiếu time → chỉ map).

> **⚠️ Khâu toạ độ (gazetteer + lat/lon) đang TẠM HOÃN — làm CUỐI** (quyết định user 2026-06-22). Lý do: độ chính xác địa điểm quan trọng + cần review kĩ (điểm yếu: địa danh trùng tên khác tỉnh bị provider chấm "cao" nhưng sai). **Tạm KHÔNG chạy `build_gazetteer.py`** (cả Google lẫn LLM). KHÔNG cần sửa/disable code: pipeline timeline (`run_timeline_index.py`) không phụ thuộc `app/indexing/geocoding/`, vẫn cho time + `locations` (tên). Builder gặp `gazetteer` rỗng → fallback chỉ-timeline, không vỡ. Nếu thấy `gazetteer` rỗng/dở dang: đó là CỐ Ý.
>
> **Đã sửa 2026-07-14 (bug thật, phát hiện khi verify UI)**: câu trên chỉ đúng khi bảng RỖNG. Thực tế `build_gazetteer.py` chưa chạy lần nào nên bảng **CHƯA TỒN TẠI** → `lookup_coords` ném `UndefinedTable` → giết CẢ `build_visualization` → mọi câu trả lời báo `Visualization lỗi: UndefinedTable` và timeline KHÔNG BAO GIỜ hiện, dù `timeline_events` có 3.674 dòng thật. Nay `lookup_coords` bắt `UndefinedTable` → trả `{}` (pattern `cost.py`), đúng tinh thần honest fallback: mất toạ độ chứ không mất timeline.

### Timeline extract theo unit — provenance CẤP CHUNK (code xong 2026-08-02, CHƯA chạy LLM)
Plan: `docs/plan/timeline-extraction-by-unit-plan.md`. Trước đây event kế thừa
`source_chunk_ids` của **cả unit** (tới 50K ký tự / hàng chục chunk) → UI cite 1 chunk vẫn
kéo về mọi event của unit. Nay LLM vẫn đọc trọn unit (đủ ngữ cảnh suy năm, giải "sau đó")
nhưng phải **quy mỗi event về chunk chứa bằng chứng**.

- **Unit giữ nguyên từng chunk** (`Unit.chunks: list[UnitChunk]`, KHÔNG còn `Unit.text` phẳng);
  prompt render `<chunk ref="N">` và LLM trả `chunk_results` — **đúng một mục cho mỗi ref**.
  `ref` (1..N) do `extract_unit_events` sinh VÀ ánh xạ ngược, một nguồn sự thật; `chunk_id`
  thật KHÔNG lộ vào prompt.
- **KHÔNG nhận kết quả một phần**: thiếu/trùng/lạ `ref`, LLM refusal, hoặc không parse được
  → `TimelineExtractionError` cho CẢ unit, không ghi cache, resume trích lại. Cache "mọi chunk
  rỗng" khi refusal = mất event VĨNH VIỄN (resume tưởng đã xong) — cố ý fail-loud.
- **Cap 50K → 30K, BỎ overlap, BỎ completeness pass lượt-2.** Overlap phá provenance (1 chunk ở
  2 unit → 2 lần gọi LLM ghi đè nhau trong cache khoá theo chunk). Cap 30K (~8K token) giữ unit
  trong vùng recall tốt nên không cần pass 2 nữa. Đo thật: **366 unit, median 5.952 ký tự,
  max 29.969, overlap 0, phủ đủ 1683/1683 chunk**.
- **Rule nhãn nhất quán (prompt §attribution)**: cùng một event kể ở nhiều `chunk_ref` phải
  dùng NGUYÊN VĂN cùng `label` + `time_start` + `locations[0]`, vì `reconcile` gộp bằng khoá
  `uuid5(parent|time|loc0|label)` — lệch chữ = hai event trùng thay vì một.
- **Cache `timeline_extractions.json` đổi khoá: `unit_id` → `chunk_id`**. `run_timeline_index.py`
  **từ chối chạy** trên cache format cũ (entry có `source_chunk_ids`) và bắt đổi tên file —
  đọc lẫn thì reconcile gán `source_chunk_ids = [unit_id]`, provenance rác vào DB.
- ⏳ **Còn nợ**: chưa chạy LLM lần nào với v4. `dataset/timeline_units.json` vẫn là bản cap 50K
  cũ và `timeline_extractions.json` vẫn là cache v2 unit-keyed → phải chạy lại BƯỚC 1 rồi đổi
  tên cache cũ trước khi trích. Bảng `timeline_events` hiện tại (3.674 dòng) vẫn là dữ liệu
  provenance-cấp-unit; chỉ replace sau khi review kết quả v4 (plan §11).

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
  `conversation.py` (conversations + messages + `count_user_messages_today`), `document.py`
  (danh mục tài liệu — nối kho thật qua `source_file`, xem `### Tài liệu` dưới),
  `inspect.py` (chunks/events cho KB Inspector), `logs.py` (conversation logs admin +
  `list_attributed_usage_rows`/`get_message_token_rows` cho token theo hội thoại),
  `cost.py` (đọc `llm_usage`, tự bắt `UndefinedTable` → `[]`), `prompt.py` (CRUD
  `managed_prompts`/`prompt_versions`: `create_staging_version`, `promote` — 1 transaction,
  demote production cũ → archived + ghi `promoted_by`/`promoted_at`). Mọi hàm SYNC; API layer
  gọi qua `anyio.to_thread`.
- `schemas/` — Pydantic request/response: `auth.py`, `chat.py`, `document.py`, `common.py`,
  `inspect.py`, `logs.py` (+ `TokenSummary`/`MessageTokens`), `user.py`, `cost.py`, `prompt.py`.
- `api/` — router: `health.py` (`/health`,`/ready`), `auth.py` (register/login/google/me/
  logout, check `is_active` ở CẢ login lẫn google), `chat.py` (conversation CRUD + `/ask` streaming — truyền `conversation_id`/
  `message_id` sang agent, gác `debug`, check quota + `GET /sources/{chunk_id}` xem toàn văn
  nguồn, xem `### Xem nguồn` dưới), `documents.py` (`/api/admin/documents*`
  — CRUD danh mục + `GET /sources` liệt kê nguồn thật trong kho),
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

### Panel tiến trình 2 tầng — DebugPanel đã XOÁ (2026-08-01)
Trước đây có **hai khối vẽ cùng một chuỗi bước bằng hai nguồn khác nhau**: panel tiến trình
(mọi người, đọc `steps`/`step`) và DebugPanel admin (đọc event `status`). Chúng vẽ LỆCH nhau
— câu xã giao hiện "1/1 bước" ở trên còn "plan + direct_response" ở dưới — và DebugPanel còn
kẹt "Đang xử lý…" vĩnh viễn ở các mục ứng với node không bao giờ chạy tới, vì event `debug`
gom một lần sát `done` nên placeholder không bao giờ được thay.

Nay gộp thành **một danh sách bước, hai tầng chi tiết**:
- **Tầng 1** (mọi người) — như cũ: nhãn bước + dòng phụ + 4 state.
- **Tầng 2** (admin) — `internals`: mảng `{label, value}` **gắn vào ĐÚNG bước sinh ra nó**,
  click dòng bước để mở. Dựng ở `orchestrator/progress.py` (thuần, ghép chuỗi bằng CODE,
  **không LLM**), gửi **ngay trong event `step`** lúc bước chạy — không gom cuối nữa.
- **Bước `visualization` MỚI**: node `build_visualization` vẫn chạy nhưng trước giờ không
  emit bước nào. Nay có dòng riêng; viz hỏng → `partial` kèm tên exception (ca `UndefinedTable`
  nuốt sạch timeline từng xảy ra một lần, xem `### Timeline + Map`). Danh sách câu đơn giờ là
  **5 dòng**: `plan → todo:N → synthesize:N → validate:N → visualization`, viz LUÔN cuối kể cả
  khi retry chèn thêm cặp synthesize/validate vào giữa.

**Gác quyền ở SERVER, 2 cửa** — agent luôn gửi `internals` (để bản lưu đủ), backend bóc:
`api/chat.py::_visible_step` gọi ở CẢ đường stream (`_proxy_stream`) lẫn đường đọc lại
(`GET /conversations/{id}`). Chặn mỗi lúc chạy rồi mở toang lúc F5 thì coi như không chặn.
Frontend KHÔNG hỏi role — điều kiện hiện tầng 2 là `internals` **có mặt**, một nguồn sự thật.
Cờ `debug` (FE gửi `debug: isAdmin`) giờ gác cả event `debug` lẫn `internals`; admin tắt debug
cũng không có tầng 2.

**Lưu vào `messages.steps`** (JSONB, **không cần DDL** — `internals` là key bên trong phần tử
mảng JSON, không phải cột). Nhờ vậy admin xem lại hội thoại **của người khác** ở `/admin/logs`
(`ConversationReplay` render `ProgressPanel` gập sẵn) — thứ DebugPanel cũ không làm được vì
ephemeral. `_merge_declaration` (backend) + `mergeDeclaration` (FE) phải chép `internals` y
như `detail`, không thì lượt soạn lại (B5) xoá trắng tầng 2 của mọi bước đã xong.

**Còn lại**: event `status` bên agent GIỮ (hữu ích khi test curl/Swagger) nhưng **frontend hết
đọc** — `statusTrace`, action `status`/`debug`, `DebugInfo`, `debugOpen`/`toggleDebug` đã xoá.
State `debug` + `AskResponse.debug` của `/ask` non-stream giữ nguyên.

### Xem nguồn (Citation Viewer) — xong 2026-07-12
Khối **Nguồn** dưới câu trả lời trước đây là chữ tĩnh (`lichsu.clean.md:7349-7352`), không
kiểm chứng được. Giờ 2 tầng, cùng khoá `chunk_id`. Plan: `docs/plan/citation-viewer-plan.md`.

- **Hover chip `[n]` → trích đoạn**, KHÔNG tốn request: `nodes.py::_make_quote` cắt 240 ký tự
  đầu chunk text (`CITATION_QUOTE_CHARS`, cắt ở ranh giới từ) → `Citation.quote` → đi kèm SSE →
  lưu luôn `messages.citations` JSONB. **Đây là trả nợ** `orchestrator-plan.md:493` (schema +
  prompt + chỗ render đã có sẵn từ lâu, chỉ thiếu code điền). KHÔNG nhờ LLM chọn quote.
- **Click chip → modal toàn văn**: `GET /api/chat/sources/{chunk_id}` (`api/chat.py`, chỉ cần
  đăng nhập — corpus là SGK, KHÔNG mật; router `/api/admin/kb/*` vẫn gác admin như cũ). Fetch
  LƯỜI lúc click vì full chunk ~2.6K ký tự, gấp ~11 lần quote — nhồi vào mọi citation của mọi
  message là phí cả SSE lẫn DB.
- **UI (`CitationList.tsx` + `groupCitations.ts` + `SourceModal.tsx`)**: KHÔNG in tên file (cả
  kho 1 file → in ra là rác) và KHÔNG in số dòng ở danh sách (chỉ hiện trong modal, cạnh toàn
  văn mới có nghĩa). Bỏ 2 thứ đó thì 2 citation cùng mục trông y hệt nhau → **buộc phải gộp
  theo `heading_path`** (gộp để ĐÚNG, không phải để đẹp), breadcrumb chung rút ra 1 dòng chân.
  Chip giữ **số thứ tự gốc** (không đánh số lại — `[n]` phải khớp `[n]` trong câu trả lời).

### Tài liệu (Module 3) — danh mục nối kho tri thức thật ("Bước 0", xong 2026-07-12)
Trước đây bảng `documents` là **sổ tay mock**: `chunk_count`/`status` do admin gõ tay, không
liên quan gì tới 1213 chunk thật trong kho. Giờ đã nối:

- **Khóa nối = `documents.source_file` ↔ `rag_chunks.metadata->>'source_file'`** (giá trị
  `lichsu.clean.md`). Chọn field này vì nó **có sẵn** trong metadata mọi chunk → **KHÔNG
  đụng `rag_chunks`/Qdrant/Neo4j/`timeline_events` một dòng nào**, không tốn API, không
  re-index. Chỉ sửa bảng `documents` (bảng backend tự quản). `metadata` cũng có
  `document_title` (= `lichsu.md`, tên tài liệu gốc) — **cân nhắc rồi và KHÔNG dùng**.
- `source_file` **immutable** (không có trong `DocumentUpdate`/`UPDATABLE_COLS`): đổi nguồn =
  đổi luôn kho chunk mà document sở hữu. UNIQUE partial index → 2 document không cùng nhận
  một nguồn (API trả 409 `source_taken`). Cột `name` chỉ là **nhãn hiển thị**, sửa thoải mái.
- **`chunk_count`/`event_count` bỏ khỏi bảng, ĐẾM THẬT lúc đọc** (`models/document.py::
  kb_counts`, event dùng toán tử mảng `&&` trên `source_chunk_ids` — cùng cơ chế
  `builder.py`). Bảng `rag_chunks` chưa tồn tại → bắt `UndefinedTable` → count 0 (pattern
  `cost.py`). Form nhập liệu **không còn ô "Số chunk"**.
- **Nguồn trong kho TỰ hiện ở danh mục** (`sync_kb_documents`, chạy đầu mỗi
  `list_documents`): chunk vào kho bằng script indexing offline chứ không qua UI, nên danh
  mục tự lấp phần thiếu — INSERT document cho `source_file` chưa có (name = tên file,
  status = `indexed`), idempotent nhờ UNIQUE index (partial → `ON CONFLICT ... WHERE
  source_file IS NOT NULL`). **KHÔNG có bước "khai báo" thủ công**, và `DocumentCreate`
  KHÔNG nhận `source_file` — form chỉ tạo tài liệu chưa gắn nguồn.
- **Xoá tài liệu còn chunk trong kho bị chặn (409 `document_indexed`)**: xoá khỏi danh mục
  là vô nghĩa vì lần load sau `sync_kb_documents` dựng lại ngay. Xoá thật = gỡ chunk khỏi
  kho → Bước 1. UI ẩn luôn nút Xoá với tài liệu có nguồn.
- `GET /api/admin/documents/sources` liệt kê nguồn CÓ THẬT trong kho → dropdown lọc ở KB
  Chunks (`GET /api/admin/kb/chunks?source_file=...`).

> **Nợ lại — "Bước 1" CHƯA code**: upload file thật (PDF/DOCX/TXT), indexing async có tiến
> độ, và **xoá cascade** (chưa có → tài liệu đã index hiện KHÔNG xoá được, xem trên).
> Hướng đã chốt cho
> Bước 1 (2026-07-12): backend **không tự chạy pipeline** (logic LLM thuộc agent-service →
> thêm endpoint `POST /index` bên agent, backend poll trạng thái); phạm vi index cho tài
> liệu mới = **vector bắt buộc, graph + timeline là checkbox tuỳ chọn** (graph extraction
> đắt nhất). Xoá cascade phải đi theo `chunk_id` qua 4 store, và ở Neo4j **chỉ xoá entity/rel
> khi mồ côi** (entity như "Hồ Chí Minh" dùng chung nhiều tài liệu).

### Frontend layout (`apps/frontend/src/`) — đã build
Vite+React 18+TS. TanStack Query (server state) + Zustand (auth/UI) + Tailwind v3 (tokens:
brand `#A4161A`, nền kem, serif+sans) + Radix + `@vis.gl/react-google-maps` +
`react-force-graph-2d` + `recharts` + `@react-oauth/google` (**PIN cứng `0.13.5`, không `^`**
— wrapper cộng đồng nằm ngay trên đường đăng nhập). Test: Vitest + Testing Library. SSE `/ask`
qua `fetch`+`ReadableStream` tay. Route công khai `/login` + `/register`; route cứng `/`
(user, sau `RequireAuth`) vs `/admin/*` (RoleGuard admin), nav admin
là **sidebar dọc theo nhóm** (`AppSidebar.tsx`, KHÔNG còn tab ngang).
- `app/` — `App.tsx` (providers + router + boot getMe), `routes.tsx` (route tree, export array;
  mỗi chức năng admin 1 route con riêng — `admin/kb/{chunks,graph,timeline}`,
  `admin/{logs,users,cost,prompts,config}`; lazy trang nặng: `kb/graph` (force-graph), `cost`
  (recharts), `prompts`; redirect back-compat từ path gộp cũ `/admin/kb`, `/admin/advanced`).
- `api/` — `client.ts` (fetch wrapper Bearer + `{code,message}`→ApiError + 401 clear),
  `askStream.ts` (⭐ parser SSE), `auth/chat/documents/kb/logs/users/cost/prompts.ts`.
- `store/` — `authStore` (persist), `chatUiStore` (`selectedEventId` link map↔timeline,
  `layoutMode` **persist** (float/split), `convDrawerOpen`, `tourPlaying`).
- `features/auth` — RequireAuth/RoleGuard/`AuthLayout` (bố cục 2 cột dùng chung 2 trang) +
  LoginForm/`RegisterForm`+`useRegister`/`GoogleButton` (bọc `GoogleOAuthProvider` TẠI CHỖ,
  không bọc toàn app) + `redirectTarget.ts` (đọc `state.from`, chặn URL ngoài).
- `features/chat` — `chatReducer` (thuần, test) + `useChat` + ChatPanel/MessageList/Bubble/
  Composer/VizPanel/`ConversationDrawer` (drawer phiên ở
  layout float) + **panel tiến trình 2 tầng**: `ProgressPanel` + `StepRow` (xem
  `### Panel tiến trình` dưới) + **xem nguồn**: `CitationList` (gộp theo mục, chip `[n]` hover ra quote) +
  `groupCitations.ts` (thuần, test kỹ — luật gộp + tiền tố chung) + `SourceModal` (click →
  toàn văn, fetch lười). `useChat` KHÔNG đụng panel bản đồ — AskPage mở theo dữ liệu.
  **Câu hỏi lại (route `ambiguous`) KHÔNG có UI riêng** (bỏ `ClarificationPrompt` 2026-08-01):
  render y như câu trả lời thường qua `content`, trả lời bằng ô nhập chính. Ô nhập riêng cũ
  trong khối vàng gọi ĐÚNG cùng `onSend` với Composer — hai ô một việc, mà ô chính không khoá
  nên không gì cho biết chúng tương đương. Còn lại: cờ `clarificationNeeded` chỉ để `ChatPanel`
  đổi placeholder thành "Trả lời để làm rõ…" khi lượt CUỐI là clarification (`clarificationQuestion`
  đã bỏ — luôn trùng `content`).
- `features/map` + `features/timeline` — EventMap (+ `CameraController` nội bộ)/EventMarker/
  MapEmptyState + TimelineBar (prop `variant` docked|overlay) + `useEventTour` (engine trình
  chiếu, có test). Honest fallback: gazetteer hoãn → markers rỗng → map nền vẫn render
  (base map là trạng thái hợp lệ), chỉ timeline có dữ liệu.

**Trang hỏi đáp (`AskPage`) — 2 bố cục, map-first** (plan: `docs/plan/map-first-layout-plan.md`):
- `float` (MẶC ĐỊNH): **bản đồ làm NỀN toàn màn hình**, card chat ĐỤC nổi bên trái (~520px),
  danh sách phiên thu vào drawer ☰, TimelineBar nổi ở đáy. `split`: layout cũ (sidebar phiên
  + chat + VizPanel + timeline docked). Nút toggle góc phải trên, `layoutMode` nhớ qua reload.
- **Camera theo DỮ LIỆU, không theo UI**: `CameraController` (trong `<APIProvider>`, vì
  `useMap()` chỉ chạy được ở đó) — viz mới → `fitBounds` cụm marker; `selectedEventId` đổi →
  `panTo`; đang tour (`tourPlaying`) → dí sát `TOUR_FOCUS_ZOOM=9`; bỏ chọn → về toàn cảnh.
  Nhờ vậy `useEventTour` KHÔNG cần chạm map instance, chỉ đẩy `selectedEventId`.
- **Trình chiếu (nút ▶ ở TimelineBar)**: kể lần lượt sự kiện theo thứ tự trục thời gian, mỗi
  bước `TOUR_STEP_MS=2500`. Tay thắng máy: user click marker/mốc khác → tour dừng. Bước "chờ
  rồi đi tiếp" là móc để cắm **text-to-speech** sau này (thay timer bằng `utterance.onend`;
  hook expose `currentEvent`) — CHƯA làm.
- `features/admin` — Module 3 Tài liệu: DocumentTable/StatusBadge/DocumentFormModal +
  `useDocuments` (`useKbSources` dùng chung cho dropdown lọc ở KB Chunks).
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
— DB mới trống sẽ fail 7 test đó (không phải lỗi code, chỉ thiếu data). **4 test
`test_activity.py` đang FAIL sẵn** vì lý do ngược lại: chúng `assert len(rows) == 1` trên
`activity_log` mà bảng đó đã tích luỹ hàng trăm dòng THẬT từ lúc chạy server (rollback của
fixture không xoá được data đã commit trước đó). Không phải lỗi code — muốn xanh thì test
phải lọc theo `request_id`, không phải theo `path`.
```powershell
$env:PYTHONIOENCODING="utf-8"
cd apps/backend
.\venv\Scripts\python.exe scripts/init_db.py        # CREATE TABLE IF NOT EXISTS 4 bảng (idempotent)
.\venv\Scripts\python.exe scripts/seed_users.py     # admin@example.com/admin123, user@example.com/user123 (dev)
.\venv\Scripts\python.exe -m uvicorn app.main:app --port 8000   # chạy server
.\venv\Scripts\python.exe -m pytest tests                       # 174 test
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

**Style bản đồ ở frontend = Cloud-based styling gắn Map ID, KHÔNG style JSON trong code**
(`styles` MapOption chỉ chạy trên raster map KHÔNG có `mapId`, mà `AdvancedMarker` lại BẮT
BUỘC `mapId` → xung khắc). Map ID **vector** tạo trên Cloud Console, style ẩn đường gắn vào
đó, code chỉ đọc `VITE_GOOGLE_MAPS_MAP_ID` (`apps/frontend/.env`). Đổi style = sửa trên
console, không cần deploy. `<APIProvider>` BẮT BUỘC `language="vi"` + `region="VN"` — mặc
định Google render "Paracel/Spratly Islands", không chấp nhận được cho đồ án lịch sử VN.

## Configuration

`.env` ở root là **nguồn cấu hình DUY NHẤT** cho monorepo; `app/core/config.py` trỏ tuyệt đối tới file đó. Mỗi app cũng có `.env.example` riêng cho local dev.

Giá trị **thực tế** trong code (đừng tin mù `.env.example`, có chỗ còn placeholder cũ):
- **Embedding + tokenizer**: model tiếng Việt `AITeamVN/Vietnamese_Embedding` (KHÔNG phải OpenAI `text-embedding-3-small` như `.env.example` để). Field: `embedding_model`, `embedding_tokenizer`.
- **LLM default**: `llm_model = "gpt-5.4-nano"` (qua gateway OpenAI-compatible, set `OPENAI_BASE_URL`). Knob riêng offline: `graph_llm_model`, `timeline_llm_model` (None = fallback `llm_model`; đặt model hỗ trợ Structured Outputs strict).
- **LLM 4 bước ONLINE — mỗi bước một model riêng, BẮT BUỘC set**: `guardrails_llm_model`, `plan_llm_model`, `resolve_llm_model`, `synthesize_llm_model` — **không field nào fallback qua field khác hay về `llm_model`** (quyết định user: chuỗi fallback cũ che mất việc đổi model trong `.env` có thật sự ăn hay không). Thiếu biến nào trong `.env` → `Settings()` vỡ ngay lúc khởi động agent-service (pydantic required field), không âm thầm chạy model không định trước. Cả 4 đều đi qua Structured Outputs strict nên model đặt vào BẮT BUỘC hỗ trợ, không degrade êm; plan/resolve còn truyền `temperature=0.0`. **Model KHÔNG quản qua `system_config`/UI admin** (quyết định cũ, giữ nguyên) — chỉ `.env` + restart agent-service. `_record_usage_from_completion` NHẬN model qua tham số chứ không tự suy lại: mỗi bước một model thì suy lại ở đó sẽ ghi nhầm model bước khác vào `llm_usage`, mà panel Token admin hiện model theo từng dòng task.
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
- `README.md` — đặc tả chức năng đầy đủ (admin, user, RAG, GraphRAG, hybrid, map, timeline, MVP scope). Nguồn truth cho scope.
- `docs/plan/` — plan đã duyệt: `chunking-embedding-plan.md` (lý do gỡ LightRAG + DIY pipeline), `llm-chunking-plan.md`, `timeline-map-plan.md` (source-of-truth timeline/map), `lichsu-headings.md`, `backend-plan.md` (kiến trúc backend gốc), `frontend-plan.md` (kế hoạch frontend đầy đủ 2 role), `backend-additions-plan.md` (Module 4 build ngay + KB Inspector + debug streaming), `admin-restructure-plan.md` (nav dọc + token theo hội thoại + quản lý Prompt — **đã code xong cả 3**, xem `### Admin nâng cao` ở trên), `system-config-plan.md` (Cấu hình hệ thống — retrieval mode + tinh chỉnh, tách riêng vì rủi ro cao, CHƯA code), `citation-viewer-plan.md` (xem nguồn: hover ra trích đoạn + click ra toàn văn, gộp citation theo mục — **đã code xong cả 3 pha**, xem `### Xem nguồn` ở trên), `map-first-layout-plan.md` (map nền + chat nổi + toggle split + trình chiếu sự kiện — **đã code xong cả 4 phase**, xem `### Frontend layout` ở trên; còn nợ user 1 việc trên Cloud Console: ẩn road ở MỌI zoom), `auth-landing-plan.md` (đăng ký công khai + landing page + đăng nhập Google — **CHƯA code**, trừ §0 rename role đã xong; xem `### Role` dưới).
- `docs/reference/google-maps-api.md` — tham chiếu Google Geocoding/Maps + ToS caching.
- `docs/design/frontend-scope.md`, `docs/brainstorming/` — scope frontend + session notes kiến trúc.
