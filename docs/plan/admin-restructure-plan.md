# Kế hoạch: Tái cấu trúc khu Admin (nav dọc + quản lý Prompt + chi phí/token theo hội thoại)

> Nguồn cảm hứng UI: bộ ảnh admin "Socratic AI" (khác domain). Chỉ mượn **cấu trúc/bố cục**,
> KHÔNG mượn màu (giữ brand `#A4161A` + nền kem). Plan này gom 3 hạng mục user chốt ngày
> 2026-07-03. Liên quan `system-config-plan.md` (Item 2 chạm orchestrator — vùng rủi ro cao).

## Quyết định đã chốt (user)

- **Item 1** — Chuyển các chức năng admin từ tab NGANG sang **nav DỌC** ở sidebar, mỗi chức
  năng 1 mục riêng, có nhóm mục như Socratic. Áp cho CẢ hai chỗ đang dùng tab ngang:
  `/admin/advanced` (4 tab) VÀ `/admin/kb` (KB Inspector — 3 tab Chunks/Đồ thị/Dòng thời gian).
- **Item 2** — Quản lý Prompt **đầy đủ**: sửa + version + đẩy production. Prompt chuyển sang
  Postgres (seed từ code hiện tại), agent đọc version `production` lúc chạy, **fallback về
  hằng trong code** nếu chưa có version active.
- **Item 3** — Trang Hội thoại **giữ nguyên** đo chất lượng (`QualitySummaryCard` +
  `QualityFlags` hiện có), **thêm** đo **token** (prompt / completion / total) song song, KHÔNG
  thay thế. **KHÔNG quy ra tiền $** (llm_usage chỉ có token). Vẫn phải gắn `conversation_id` +
  `message_id` vào `llm_usage` để quy token về từng hội thoại/message.

---

## Item 1 — Nav dọc, tách route (thuần frontend, an toàn, làm TRƯỚC)

### Hiện trạng
- `apps/frontend/src/pages/AdminAdvancedPage.tsx`: 1 route `/admin/advanced` chứa 4 Radix Tab
  (`logs` / `users` / `cost` / `config`).
- `apps/frontend/src/pages/AdminKbPage.tsx`: 1 route `/admin/kb` chứa 3 Radix Tab
  (`chunks` / `graph` / `timeline`), hiện có điều hướng chéo qua `chunk_id`
  (navChunk/navEntity/navEvent đổi tab).
- `AppSidebar.tsx`: `NAV_ITEMS` danh sách phẳng, chưa có nhóm.

### Việc làm
1. **`AppSidebar.tsx`**: thêm field `group?: string` cho `NavItem`. Khi sidebar mở → render
   nhãn nhóm viết hoa (xám nhỏ) trước item đầu mỗi nhóm; khi thu gọn → chỉ icon, có
   divider mảnh giữa nhóm. Cấu trúc nav mới:
   - *(không nhóm)* `Hỏi đáp` → `/`
   - **NỘI DUNG**: `Tài liệu` → `/admin/documents`
   - **KHO TRI THỨC**: `Đoạn tài liệu` → `/admin/kb/chunks`, `Đồ thị tri thức` →
     `/admin/kb/graph`, `Dòng thời gian` → `/admin/kb/timeline`
   - **QUẢN TRỊ**: `Hội thoại & chi phí` → `/admin/logs`, `Người dùng & quota` →
     `/admin/users`, `Chi phí` → `/admin/cost`, `Quản lý Prompt` → `/admin/prompts`,
     `Cấu hình hệ thống` → `/admin/config`
   - Icon (lucide, đã có sẵn trong dep): `FileStack`, `Share2`, `CalendarClock`,
     `MessagesSquare`, `Users`, `Coins`, `Wand2`/`FileCode2`, `SlidersHorizontal`.
2. **`routes.tsx`**:
   - Bỏ route `advanced` gộp, thêm 5 route con `/admin`: `logs` / `users` / `cost` /
     `prompts` / `config`. `index` redirect `/admin` → `/admin/logs`.
   - Bỏ route `kb` gộp, thêm 3 route con `/admin/kb`: `chunks` / `graph` / `timeline`.
     Redirect `/admin/kb` → `/admin/kb/chunks`.
   - Back-compat redirect: `advanced` → `/admin/logs`.
   - Lazy-load trang nặng: `cost` (recharts), `prompts` (editor), `graph` (react-force-graph-2d).
3. **Page wrappers mới** (mỏng, chỉ bọc component tab đã có):
   - `pages/AdminLogsPage.tsx` → `ConversationsTab` (bản Item 3, xem dưới)
   - `pages/AdminUsersPage.tsx` → `<UsersTab/>`
   - `pages/AdminCostPage.tsx` → `<CostTab/>` (lazy)
   - `pages/AdminConfigPage.tsx` → `<ConfigTabStub/>`
   - `pages/AdminPromptsPage.tsx` → mới (Item 2, lazy)
   - `pages/AdminKbChunksPage.tsx` / `AdminKbGraphPage.tsx` / `AdminKbTimelinePage.tsx` →
     bọc `ChunksTab` / `GraphTab` / `TimelineTab`.
4. **KB — BỎ điều hướng chéo** (user chốt 2026-07-03): mỗi trang KB độc lập, chỉ quản selection
   nội bộ. Không cần truyền id qua URL/route. Gỡ chuỗi props `onNavChunk`/`onNavEntity`/
   `onNavEvent` ở CẢ 2 tầng:
   - Tab: `ChunksTab` / `GraphTab` / `TimelineTab`.
   - Detail (nơi render link nhảy thật): `ChunkDetail` / `EntityDetail` / `EventDetail` —
     các tham chiếu `chunk_id`/entity/event đổi từ link bấm-được thành text thường (vẫn hiện
     id để tra cứu, chỉ bỏ hành vi nhảy tab).
5. **Xoá** `AdminAdvancedPage.tsx` + `AdminKbPage.tsx` (thay bằng route con + redirect). Mỗi
   page tự có header "tiêu đề + 1 dòng mô tả mục đích" (học từ Socratic) — component
   `<PageHeader title desc/>` chung.

### Kiểm thử
- `npm run typecheck` + `npm run test`. Không có test nào phụ thuộc `AdminAdvancedPage`/route
  `advanced` (đã grep — 0 test dính). Kiểm test KB có phụ thuộc điều hướng chéo không → sửa
  cho khớp việc bỏ cross-nav. Thêm test render sidebar có đủ nhóm mục cho admin.

---

## Item 3 — Hội thoại theo token (làm THỨ HAI: cần schema + luồn id)

### Vì sao khả thi rẻ
Backend `chat.py::ask` **đã** pre-generate `assistant_id = uuid4()` (dòng 206) và có `conv.id`.
Chỉ cần chuyển 2 giá trị này xuống agent → orchestrator state → `record_usage`. Không cần
đổi timing/流程.

### Thay đổi backend gateway
- **`services/agent_client.py`**: `AgentAskRequest` thêm `conversation_id: str | None`,
  `message_id: str | None`.
- **`api/chat.py::ask`**: khi tạo `AgentAskRequest` truyền `conversation_id=conv.id`,
  `message_id=assistant_id` (id đã pre-generate). Không đổi gì khác.

### Thay đổi agent-service
- **`schemas/ask.py::AskRequest`**: thêm `conversation_id: str | None = None`,
  `message_id: str | None = None` (backend tự điền, giống `user_id`).
- **`orchestrator/state.py` (AgentState)** + **`orchestrator/runner.py`**: mang
  `conversation_id`, `message_id` vào state (giống `user_id` đang có).
- **`core/usage_log.py`**:
  - DDL: thêm cột `conversation_id TEXT`, `message_id TEXT`. `ensure_llm_usage_table` chạy
    thêm `ALTER TABLE llm_usage ADD COLUMN IF NOT EXISTS ...` (idempotent, GIỮ dữ liệu cũ —
    llm_usage là log rẻ, KHÔNG drop). Index: `CREATE INDEX IF NOT EXISTS
    llm_usage_message_id_idx ON llm_usage(message_id)`.
  - `record_usage(...)` thêm tham số `conversation_id`, `message_id` → cột INSERT.
- **`orchestrator/nodes.py`**: mọi call site online của `record_usage` truyền thêm 2 id lấy
  từ state:
  - `_record_usage_from_completion` (build_query) — thêm 2 tham số.
  - `synthesize::_on_usage`.
  - `guard_input` → `check_input` (guardrails input classifier cũng ghi usage, `task=
    "guardrail_input"`) — luồn 2 id xuống `orchestrator/guardrails.py` record_usage.
  → Nhờ vậy 1 message trả lời gom được nhiều dòng usage (task `build_query` + `synthesize` +
    `guardrail_input`) → phân rã theo `task`.

> Lưu ý dữ liệu: message/usage CŨ (trước thay đổi) `message_id = NULL` → không quy được về
> message. Chấp nhận (chỉ áp cho câu hỏi MỚI). Không backfill.

> **Edge blocked/lỗi giữa stream**: `chat.py::_proxy_stream` forward event `blocked` **KHÔNG
> kèm** `conversation_id`/`message_id` (khác `done`) — xem `chat.py:152`. Message an toàn vẫn
> persist bằng `assistant_id` qua `_persist_assistant` (`chat.py:145`), TRỪ khi không có
> content thì trả `None`. Nên guardrail usage có thể mang `message_id=assistant_id` mà message
> KHÔNG tồn tại (orphan). Đây chính là lý do `get_message_usage` dùng LEFT JOIN + tolerate ở
> trên. Admin reload logs vẫn thấy (message ở DB nếu đã persist); realtime FE không link được
> message blocked — chấp nhận, không cần đổi luồng blocked.

### Bộ chỉ số hiển thị (gọn — chỉ cái quan trọng, CỘNG THÊM bên cạnh chất lượng, không thay)
- **Danh sách hội thoại** (mỗi dòng): giữ cột chất lượng hiện có, **thêm cột** tổng token của
  hội thoại + số lượt hỏi. Sort theo token giảm dần (tuỳ chọn) hoặc theo thời gian (mặc định).
- **Card tổng đầu tab**: giữ nguyên `QualitySummaryCard`, **thêm** `TokenSummaryCard` đặt cạnh
  (không thay thế): Tổng lượt gọi LLM · Token vào · Token ra · Tổng token · Token TB/lượt
  (dùng `<StatCard>` chung). **Quyết định khi code (khác bản nháp point A)**: trên tab Hội thoại
  card + danh sách đều SUM **chỉ usage đã gắn `conversation_id`** trong khoảng ngày → card ==
  tổng danh sách (nhất quán, không gây khó hiểu). **Honest total gồm cả row cũ
  `conversation_id=NULL`** đã có sẵn ở **tab Chi phí** (`/admin/cost`) nên không lặp lại ở đây;
  card token ghi rõ "đã gắn hội thoại". Endpoint `token-summary` chỉ lọc theo ngày (giống
  `quality-summary`), không theo `user_email`.
- **Chi tiết 1 hội thoại**: giữ nguyên `QualityFlags` trong `ConversationLogDetail`, **thêm**
  khối token/task breakdown mỗi message: token vào / ra / tổng của message đó + **phân rã theo
  task** — raw task thực tế trong code chỉ có 3: `build_query`, `synthesize`, `guardrail_input`
  (KHÔNG phải `guardrail_classifier`). **Model hiển thị Ở TỪNG DÒNG TASK, không phải 1 model
  chung cho message** (build_query/synthesize dùng `_orchestrator_model()`, guardrail_input
  dùng `guardrails_llm_model` — khác nhau trong cùng 1 message).

> **Nhãn task**: lưu **raw task nguyên** trong DB (đừng đổi tên khi ghi). FE map sang nhãn
> tiếng Việt qua dict cố định (`build_query`→"Dựng truy vấn", `synthesize`→"Tổng hợp",
> `guardrail_input`→"Kiểm duyệt"); task lạ không có trong dict → hiện raw (an toàn khi thêm
> task mới sau này).

### Thay đổi backend read model + API
- **`models/logs.py`**: thêm hàm join `messages` ↔ `llm_usage` theo `message_id`. **Cả 2 hàm
  PHẢI bắt `psycopg.errors.UndefinedTable` → trả `[]`** y hệt `models/cost.py:49,72` — vì
  `llm_usage` tạo lazy trong `record_usage`, admin mở tab Hội thoại trước câu hỏi đầu tiên (DB
  mới) sẽ 500 nếu không bắt.
  - `list_attributed_usage_rows(from_date, to_date)` — rows usage CÓ `conversation_id` (bỏ NULL
    lịch sử) trong khoảng ngày. `token_service.compute_token_summary` gom ra `overall` (card) +
    `by_conversation` (cột token danh sách). Nguồn = **`llm_usage` trực tiếp**, KHÔNG join
    `messages` → orphan usage vẫn vào tổng hội thoại.
  - `get_message_token_rows(conversation_id)` — usage 1 hội thoại gộp theo `(message_id, task,
    model)` cho breakdown. Đọc thẳng `llm_usage WHERE conversation_id` (KHÔNG join `messages`);
    FE map theo `message_id`, dòng không khớp message hiển thị (orphan) chỉ đơn giản không hiện
    dưới message nào. **Hệ quả chấp nhận**: tổng per-message có thể KHÔNG bằng đúng total hội
    thoại khi có orphan.
- **`services/`**: thêm `token_service.py` (hàm thuần, không I/O — idiom `cost_service.py`)
  gom rows → summary + per-conversation + per-message breakdown. Unit-test không cần DB.
- **`schemas/logs.py`** (hoặc file mới): thêm model token summary / breakdown.
- **`api/logs.py`**: endpoint mới `/api/admin/logs/token-summary`,
  `/api/admin/logs/{id}/tokens` (hoặc nhét token vào detail hiện có). Endpoint quality cũ giữ
  nguyên, FE vẫn dùng song song.

### Thay đổi frontend
> **Cập nhật khi code (user chốt 2026-07-05)**: trang Hội thoại **redesign sang bố cục 3 cột
> inline** kiểu Socratic (mượn BỐ CỤC, giữ nội dung của mình — KHÔNG bịa metric downvote/mastery
> mà hệ không có). Bỏ table + modal cũ.
- `features/advanced/LogsTab.tsx`: giữ `QualitySummaryCard` + `TokenSummaryCard` (2 section card
  trên đầu) + `LogsFilterBar`. Dưới là **grid 3 cột**:
  - **Trái** `ConversationSessionList` — danh sách phiên chọn được (user · tiêu đề · số lượt ·
    token) + `Pagination`. Auto-chọn phiên đầu.
  - **Giữa** `ConversationReplay` — replay hội thoại inline (bong bóng user + assistant render
    `Markdown` + `ConfidenceBadge`).
  - **Phải** `ConversationDetailPanel` — 2 tab **Chất lượng** (`QualityFlags` mỗi lượt) / **Token**
    (breakdown task/model mỗi lượt). Giữ CẢ hai (song song, không thay thế).
- **Xoá** `ConversationLogTable.tsx` + `ConversationLogDetail.tsx` (thay bằng 3 component trên).
- `api/logs.ts` + `types/admin.ts`: thêm type token.

### Kiểm thử
- Agent: test `record_usage` ghi đúng 2 cột mới; test node truyền id (mock).
- Backend: test `token_service` thuần (rows → summary/breakdown). Test API join.
- E2E thủ công: hỏi 1 câu mới → mở tab Hội thoại → thấy token per message + phân rã task.

---

## Item 2 — Quản lý Prompt đầy đủ (làm CUỐI: lớn nhất + chạm orchestrator)

> ⚠️ Vùng rủi ro (`system-config-plan.md`). Nguyên tắc an toàn: **luôn fallback về hằng code**
> nếu DB chưa có version production → kể cả DB hỏng, answer flow KHÔNG vỡ.

### Prompt nào được quản lý
Prompt = **phần system prompt tĩnh** (khối `<role>/<task>/<rules>` trong `app/prompts/*.py`).
Phần lắp ráp động (`build_user_prompt`, render chunk/graph) VẪN ở code.

- **Phase này wiring runtime cho 3 prompt ONLINE** (orchestrator dùng mỗi câu trả lời):
  `build_query` (`SYSTEM_PROMPT`), `synthesize` (`SYSTEM_PROMPT`), `guardrails_input` (system).
- Prompt OFFLINE (`graph_extract`, `metadata_extract`, `timeline_extract`, `geocode`,
  `alias_judge`): **đăng ký + version được trong DB** để UI hiện đủ nhóm như Socratic, nhưng
  **wiring vào script indexing HOÃN** (chỉ ảnh hưởng lúc re-index, ghi rõ "chưa nối"). Tránh
  mở rộng bề mặt thay đổi sang pipeline indexing trong phase này.

### Schema (Postgres) — nguồn: agent-service (runtime), backend đọc/ghi cùng DB
Store mới `apps/agent-service/app/tools/prompts/prompt_store.py` (mirror `chunk_store.py`,
lazy `CREATE TABLE IF NOT EXISTS`):

```
managed_prompts(
  key         TEXT PRIMARY KEY,     -- 'build_query' | 'synthesize' | 'guardrails_input' | ...
  grp         TEXT NOT NULL,        -- 'ONLINE' | 'GUARDRAIL' | 'INDEXING'
  title       TEXT NOT NULL,
  description TEXT,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)
prompt_versions(
  id           UUID PRIMARY KEY,
  prompt_key   TEXT NOT NULL REFERENCES managed_prompts(key),
  version_no   INTEGER NOT NULL,     -- tăng dần theo prompt_key
  content      TEXT NOT NULL,        -- system prompt text
  note         TEXT,
  status       TEXT NOT NULL,        -- 'production' | 'staging' | 'archived'
  created_by   TEXT,                 -- email admin tạo version
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  promoted_by  TEXT,                 -- email admin đẩy lên production (NULL nếu chưa từng)
  promoted_at  TIMESTAMPTZ,          -- lúc đẩy production gần nhất (NULL nếu chưa từng)
  UNIQUE(prompt_key, version_no)
)
-- Ràng buộc mềm ở tầng app: mỗi prompt_key có TỐI ĐA 1 version status='production'.
-- promoted_by/promoted_at: audit tối thiểu "ai đẩy bản nào lúc nào" — đủ debug lúc demo,
-- rẻ hơn bảng audit event riêng.
```

### Seed (chạy 1 lần, idempotent)
Script `apps/agent-service/scripts/seed_prompts.py`: với mỗi prompt key, nếu chưa có row →
tạo `managed_prompts` + 1 `prompt_versions` (version_no=1, status='production',
content = hằng trong code hiện tại, note='seed from code'). Chạy lại không tạo trùng.

### Runtime loader (agent-service)
`prompt_store.py::get_active_prompt(key, *, fallback: str) -> str`:
- Đọc `content` của version `status='production'` mới nhất theo key.
- Không có / DB lỗi → trả `fallback` (hằng code). **Nuốt lỗi** (giống `record_usage`).
- Cache in-memory TTL ngắn (≈60s) để không query DB mỗi câu; đổi prompt trễ tối đa ~60s
  (chấp nhận được; hoặc bust cache khi promote — làm sau).
- Call site đổi trong `orchestrator/nodes.py`:
  `bq_prompt.SYSTEM_PROMPT` → `get_active_prompt("build_query", fallback=bq_prompt.SYSTEM_PROMPT)`;
  tương tự `synthesize`, `guardrails_input`.

### Backend API (admin CRUD) — `apps/backend/app/`
- `models/prompt.py` (psycopg trực tiếp, đọc/ghi cùng bảng — pattern `cost.py`):
  `list_prompts()`, `get_prompt(key)` + versions, `create_staging_version(key, content, note, by)`,
  `promote(key, version_no, by)` (transaction: demote production→archived, set no→production
  **+ set `promoted_by=by`, `promoted_at=now()` trên version được đẩy**),
  `get_version(key, version_no)`.
- `schemas/prompt.py`: Pydantic list/detail/version/compare.
- `api/prompts.py` (router `/api/admin/prompts`, `require_admin`):
  - `GET /` → list nhóm (key, grp, title, active version_no, số version).
  - `GET /{key}` → meta + versions[] (kèm `promoted_by`/`promoted_at`) + content production
    hiện hành.
  - `POST /{key}/versions` `{content, note}` → tạo staging (`created_by` = admin hiện tại).
  - `POST /{key}/versions/{no}/promote` → đẩy production (`promoted_by` = admin hiện tại).
  - `GET /{key}/versions/{no}` → content 1 version (phục vụ So sánh).
- Đăng ký router trong `app/main.py`.

### Frontend — `apps/frontend/src/`
- `api/prompts.ts` + `types` cho prompt.
- `features/prompts/` (3 cột như ảnh Socratic prompts-detail):
  - **Trái** `PromptTree`: list theo nhóm (ONLINE / GUARDRAIL / INDEXING) + chọn.
  - **Giữa** `PromptEditor`: header (key · nhóm · badge PRODUCTION · cập nhật bởi) + textarea
    `content` + ô `note` ("why this change?") + nút **Lưu bản staging** + **Đẩy lên production**.
  - **Phải** `VersionHistory`: mỗi version có badge `PRODUCTION`/`STAGING`/`ARCHIVED` +
    "Hiện hành" + dòng audit nhỏ ("tạo bởi {created_by} · đẩy bởi {promoted_by} lúc
    {promoted_at}", ẩn khi NULL) + nút **Đẩy lên production** + **So sánh** (mở Modal diff 2
    cột, dùng lib diff nhẹ hoặc so sánh dòng tự viết).
- `pages/AdminPromptsPage.tsx` (lazy) lắp 3 cột.
- Prompt OFFLINE hiện badge "chưa nối runtime" để trung thực (chỉ có hiệu lực khi re-index).

### Kiểm thử
- Agent: `get_active_prompt` trả production / fallback khi thiếu / nuốt lỗi DB. Seed idempotent.
- Backend: promote đổi đúng status (transaction), create_staging tăng version_no, list nhóm.
- FE: render tree/editor/history; mutation tạo staging + promote invalidate query.
- E2E thủ công: sửa `synthesize` → đẩy production → hỏi câu mới → answer dùng prompt mới
  (kiểm bằng debug panel / thay đổi rõ). Xoá version production → answer fallback về code.

---

## Thứ tự thực hiện & rủi ro

1. **Item 1** (nav dọc) — thuần FE, không đụng backend/agent. Merge được ngay, giảm rối UI.
2. **Item 3** (token/hội thoại) — schema log rẻ + luồn id; rủi ro thấp (record_usage nuốt lỗi).
3. **Item 2** (prompt) — lớn nhất, chạm orchestrator; làm sau cùng, bọc fallback an toàn.

### Ranh giới KHÔNG làm trong plan này
- KHÔNG quy token ra tiền $ (user chọn token-only).
- KHÔNG wiring prompt OFFLINE vào script indexing (chỉ lưu/version trong DB).
- KHÔNG đụng `rag_chunks`/Qdrant/Neo4j/`timeline_events` (chỉ `llm_usage` + 2 bảng prompt mới).
- KHÔNG làm phần "Cấu hình hệ thống" khác (retrieval mode mặc định...) — vẫn stub.
- KHÔNG backfill usage cho message cũ.

### File đụng tới (tổng hợp)
- FE: `AppSidebar.tsx`, `routes.tsx`, 5 page wrapper, `features/advanced/*` (rework logs),
  `features/prompts/*` (mới), `api/{logs,prompts}.ts`, `types/admin.ts`, component
  `PageHeader`/`StatCard` chung.
- Backend: `services/agent_client.py`, `api/chat.py`, `models/{logs,prompt}.py`,
  `services/token_service.py`, `schemas/{logs,prompt}.py`, `api/{logs,prompts}.py`, `main.py`.
- Agent: `schemas/ask.py`, `core/usage_log.py`, `orchestrator/{state,runner,nodes,guardrails}.py`,
  `tools/prompts/prompt_store.py` (mới), `scripts/seed_prompts.py` (mới).
```
