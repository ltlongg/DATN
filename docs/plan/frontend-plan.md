# Plan Frontend — Agentic RAG Lịch Sử Việt Nam

## Context

Frontend hiện chỉ là **scaffold rỗng** (`apps/frontend/src/{app,pages,features,api,types,components}` toàn `.gitkeep`). **Chưa có `package.json`/`vite.config.ts`/`tsconfig.json`** ở gốc `apps/frontend` — `node_modules` hiện có sẵn `react`/`react-dom`/`react-router-dom`/`vite` nhưng thiếu file cấu hình gốc nên project **chưa init xong**, `npm run dev` chưa chạy được cho tới khi làm bước 0 (xem "Thứ tự triển khai"). Backend + agent-service đã build thật và sẵn sàng cho frontend tiêu thụ. Mục tiêu: dựng frontend phủ **cả 2 role** (user + admin), nối API thật, với một yêu cầu mới: **khung chat của admin có debug view** để admin theo dõi luồng hoạt động của agent chi tiết, còn user chỉ hỏi đáp bình thường.

> **Cập nhật 2026-07-01**: `docs/plan/backend-additions-plan.md` đã **code xong toàn bộ Phần 1–4** (debug streaming, read endpoints Module 5, 3/4 nhóm Module 4) và đã verify khớp code thật (endpoint/field/logic — không có sai lệch so với plan). Plan frontend này giờ **không còn phần nào "chờ backend"** ngoài Cấu hình hệ thống (`system-config-plan.md`, cố ý làm sau cùng) — mọi API ở bảng phân pha dưới đây đều đã sẵn sàng dùng ngay, không cần đợi thêm.

Plan phủ toàn bộ chức năng 2 role, **không còn phân pha theo "chờ backend"** (trừ Cấu hình hệ thống): Module 4 (admin nâng cao) 3/4 nhóm đã có endpoint build thật (Hội thoại & chất lượng, Người dùng & quota, Chi phí); Module 5 (KB Inspector) đã có read endpoint; nhóm Cấu hình hệ thống đã có plan nhưng chưa build (tách sang `system-config-plan.md`).

> **Phần backend đã hoàn thành** (tham khảo khi cần chi tiết implement/test): **`docs/plan/backend-additions-plan.md`** (debug streaming, read endpoints Module 5, đặc tả API Module 4 — tất cả ĐÃ CODE, xem file đó để biết chi tiết implementation nếu cần). Riêng **Cấu hình hệ thống** (retrieval mode selector + tinh chỉnh retrieval/synthesize) tách hẳn sang **`docs/plan/system-config-plan.md`** — nặng/rủi ro nhất, làm SAU KHI các phần khác xong; trong lúc chờ, tab tương ứng ở admin hiện "Sắp cập nhật". Plan này chỉ nói phần **frontend**.

> **Thuật ngữ**: role không-phải-admin gọi là **"user" / "người dùng"** trong toàn bộ plan & UI. Lưu ý: **giá trị literal trong code backend vẫn là `teacher`** (`Role = admin|teacher`, seed `teacher@example.com`) — giữ nguyên ở các chỗ là giá trị code; "user" chỉ là cách gọi ở mô tả/giao diện.

Tài liệu nguồn: `README.md` (§1–20, scope gốc), `docs/design/frontend-scope.md` (scope đã chốt + layout), `CLAUDE.md` (kiến trúc 3-service), `docs/plan/backend-additions-plan.md` (API bổ sung).

---

## Quyết định đã chốt

- **Phạm vi**: phủ toàn bộ cả Module 4 (admin nâng cao), nhưng phân pha — **3/4 nhóm** (Hội
  thoại & chất lượng, Người dùng & quota, Chi phí) build thật ngay; **Cấu hình hệ thống** tách
  plan riêng (`system-config-plan.md`), làm SAU, tab admin hiện "Sắp cập nhật".
- **Chi phí = dashboard thật** (không còn stub): token usage 2 lệnh gọi LLM online
  (`build_query`/`synthesize`) theo ngày/tác vụ/user. Ước tính $ tính CLIENT-SIDE (admin tự
  nhập giá/1K token, không lưu backend, không phải giá thật từ nhà cung cấp). Xem
  `backend-additions-plan.md` §Phần 4.
- **Cấu hình hệ thống** (khi tới lượt làm) sẽ KHÔNG phải trình xem read-only kiểu Module 5 —
  bấm "Lưu & áp dụng" có hiệu lực THẬT ngay lượt hỏi tiếp theo. Spec đầy đủ (kể cả
  `RetrievalModeSelect` cho user chọn mode per-câu-hỏi) đã có sẵn ở `system-config-plan.md`,
  không cần thiết kế lại khi build.
- **Tech stack**: TanStack Query (data-fetching/cache) + Zustand (auth/UI state) + Tailwind CSS (+ Radix primitives kiểu shadcn cho form/dialog/badge) + `@vis.gl/react-google-maps` (wrapper Google Maps chính thức) + timeline component tự viết + `react-force-graph-2d` (ego-graph cho Module 5) + `recharts` (biểu đồ cho dashboard Chi phí — bar/line theo ngày, breakdown theo tác vụ). SSE `/ask` xử lý bằng `fetch` + `ReadableStream` tay (EventSource không gửi được Bearer header).
- **Debug view (admin)**: mức **đầy đủ** = status events + debug data (standalone_query, route, entities seed, số chunk/graph, retrieval_mode, confidence, citations, warnings). Backend đã pipe `debug` qua stream (đã code + verify) → xem `backend-additions-plan.md` §1.
- **Vị trí debug UI**: **panel gập (collapsible) dưới mỗi câu trả lời assistant** trong khung chat admin.
- **Trình xem kho tri thức (Module 5, admin)**: **read-only** — xem/tìm/lọc chunk (`rag_chunks`), entity+quan hệ (Neo4j `:Entity`/`:REL`, ego-graph), timeline event (`timeline_events`) trực tiếp trên web thay vì mở Neo4j Browser / psql. KHÔNG sửa/xóa (tránh desync Postgres↔Qdrant↔Neo4j). Read endpoint đã code xong → xem `backend-additions-plan.md` §2. Graph viz dùng `react-force-graph-2d`.

---

## Phân pha (mọi API đã sẵn sàng, trừ C3)

| Pha | Màn hình / Tính năng | Backend status | Hành động FE |
|-----|----------------------|----------------|--------------|
| **A** | Đăng nhập, Hỏi đáp (chat + multi-turn sidebar), Quản lý tài liệu, **Debug view admin** | ✅ Đã code + verify (event `debug` emit đúng shape, backend ép `debug=False` cho non-admin) | Code đầy đủ, nối API thật |
| **B — UI shell, data thưa** | Map + Timeline trong trang Hỏi đáp | ⚠️ Contract `VisualizationPayload` có, nhưng **gazetteer hoãn → `markers` rỗng**, chỉ `timeline` có data (đây là quyết định cố ý riêng, không liên quan Phần 1–4 đã xong) | Dựng đủ UI, honest-fallback khi `markers` rỗng; cắm marker thật khi geocoding bật lại |
| **A+** | **Module 5 — Trình xem kho tri thức** (chunk / graph / timeline, read-only) | ✅ Đã code đủ `/api/admin/kb/*` (backend) + `/kb/entities*` (agent-service) | Dựng inspector đầy đủ ngay, nối API thật |
| **C1** | Module 4: Hội thoại & chất lượng, Người dùng & quota, Chi phí (cost dashboard) | ✅ Đã code đủ `/api/admin/logs/*`, `/api/admin/users*`, `/api/admin/cost/*` | Code đầy đủ, nối API thật |
| **C3 — Sắp cập nhật (plan riêng)** | Module 4: Cấu hình hệ thống (retrieval mode selector + tinh chỉnh retrieval/synthesize) + `RetrievalModeSelect` trong khung chat | ⚠️ Đã có plan đầy đủ nhưng CHƯA build — xem `docs/plan/system-config-plan.md` | Tab hiện "Sắp cập nhật"; build SAU khi FE (A, A+, C1) xong |

**Nguyên tắc bắt buộc (từ frontend-scope §⚠️)**: admin/user **tách route cứng** (`/` user, `/admin/*` admin), gác cổng cả FE lẫn BE; user KHÔNG thấy menu admin; admin vào khu user *như một user*; hai khu không hiển thị đồng thời.

---

## API contract frontend tiêu thụ (đã verify trong code, cập nhật 2026-07-01)

Base URL: `VITE_API_BASE_URL` (mặc định `http://localhost:8000`). JWT Bearer trong header `Authorization`. Toàn bộ endpoint dưới đây **đã code xong** (không còn phần nào chờ backend, trừ mục Cấu hình hệ thống cuối bảng).

**Auth** (`apps/backend/app/api/auth.py`)
- `POST /api/auth/login` → `{access_token, token_type:"bearer", user:{id,email,name,role}}` (role ∈ `admin|teacher`); tài khoản `is_active=false` → **403 `account_locked`** ngay ở login (không cấp token mới)
- `GET /api/auth/me` → `UserPublic`
- `POST /api/auth/logout` → no-op (client xóa token)
- Mọi request có token (qua `get_current_user`) cũng re-check `is_active` → **403 `account_locked`** dù token còn hạn (khóa có hiệu lực ngay, không cần user logout)

**Chat** (`apps/backend/app/api/chat.py`)
- `GET /api/chat/conversations` → `ConversationOut[]`
- `POST /api/chat/conversations` `{title?}` → `ConversationOut`
- `GET /api/chat/conversations/{id}` → `ConversationDetail{...,messages:MessageOut[]}`
- `POST /api/chat/conversations/{id}/ask` `{question, debug}` → **SSE** `text/event-stream`
  - `debug` FE gửi `true` chỉ có tác dụng khi role=`admin`; backend ép `False` cho `teacher`
    (`debug = body.debug and user.role == "admin"` — `chat.py`) nên user gửi `true` vẫn không
    nhận event `debug`.
  - **Quota**: nếu `user.question_quota` không null và số câu hỏi hôm nay (giờ Postgres) đã
    ≥ quota → **429 `quota_exceeded`** ngay khi gọi (trước khi mở stream, câu hỏi KHÔNG được
    lưu). Câu hỏi đầu tiên trong ngày luôn được phép dù `question_quota=1`.
  - field `retrieval_backend?` — **CHƯA build**, xem `docs/plan/system-config-plan.md`; khi
    build xong sẽ optional, mọi role dùng được, KHÔNG gác `admin` như `debug`

**Admin documents** (`apps/backend/app/api/documents.py`, chặn cứng `require_admin`)
- `GET|POST /api/admin/documents`, `PATCH|DELETE /api/admin/documents/{id}`
- `DocumentStatus ∈ draft|indexing|indexed|failed`

**Admin KB Inspector (Module 5)** — ✅ đã code (`apps/backend/app/api/inspect.py` +
`apps/agent-service/app/api/kb.py`), prefix backend `/api/admin/kb`:
- `GET /api/admin/kb/chunks?q&heading&limit(1-200,default 50)&offset` →
  `{items: ChunkListItem[], total, limit, offset}`. Search `text ILIKE %q%`; sort
  `chunk_index ASC NULLS LAST, chunk_id ASC`.
- `GET /api/admin/kb/chunks/{chunk_id}` → `ChunkDetail` (`text` đầy đủ + `metadata` +
  `heading_path` + `referencing_events: EventRef[]` — event nào tham chiếu chunk này, đã join
  sẵn phía backend). *Lưu ý: chunk detail KHÔNG trả entity tham chiếu trực tiếp — muốn xem
  entity liên quan tới 1 chunk, gọi riêng `GET /api/admin/kb/entities?chunk_id=...` (xem
  dưới).*
- `GET /api/admin/kb/events?q&confidence&limit(1-200,default 50)&offset` →
  `{items: EventListItem[], total, limit, offset}`. Search `label`/`summary`; sort
  `time_start ASC NULLS LAST, label ASC`.
- `GET /api/admin/kb/events/{event_id}` → `EventDetail` (thêm `summary`, `parent_event_norm`,
  `source_chunk_ids[]` so với list item).
- `GET /api/admin/kb/entities?q&type&chunk_id&limit(1-200,default 50)&offset` → proxy sang
  agent-service `GET /kb/entities`, trả `{items: EntityListItem[], total, limit, offset}`.
  Truyền `chunk_id=<id>` (không kèm `q`/`type`) để lấy đúng entity tham chiếu 1 chunk — đây là
  cách "chunk → entity" hoạt động (khác cơ chế với `referencing_events` ở trên, vì entity nằm
  ở Neo4j còn event nằm ở Postgres).
- `GET /api/admin/kb/entities/{norm_name}` → proxy `GET /kb/entities/{norm_name}` → `EntityDetail`
  (`descriptions[]`, `source_chunk_ids[]`, `neighbors: EntityNeighbor[]`,
  `edges: EntityEdge[]` — dùng dựng ego-graph 1-hop).

**Admin Module 4** — ✅ đã code (`apps/backend/app/api/{logs,users,cost}.py`):
- `GET /api/admin/logs/conversations?user_email&from_date&to_date&limit(1-200,default 50)&offset`
  → `{items: ConversationLogItem[], total, limit, offset}`
- `GET /api/admin/logs/conversations/{id}` → `ConversationLogDetail{...,
  messages: MessageLogItem[]}` — mỗi message kèm `quality: MessageQuality` tính sẵn phía backend
- `GET /api/admin/logs/quality-summary?from_date&to_date` → `QualitySummary`
- `GET /api/admin/users` → `UserOut[]`
- `POST /api/admin/users` `UserCreate` → `UserOut` (201); email trùng → 409 `conflict`
- `PATCH /api/admin/users/{id}` `UserUpdate` (partial) → `UserOut`; admin tự đặt
  `is_active=false` cho chính mình → **400 `self_lock_forbidden`**
- `GET /api/admin/cost/overview?from_date&to_date` → `CostOverview`
- `GET /api/admin/cost/by-day?from_date&to_date` → `DailyCost[]`
- `GET /api/admin/cost/by-task?from_date&to_date` → `TaskCost[]`
- `GET /api/admin/cost/top-users?from_date&to_date&limit(1-100,default 10)` → `TopUserCost[]`
- Cả 4 endpoint cost đều **an toàn khi bảng `llm_usage` chưa tồn tại** (chưa có câu hỏi nào
  qua flow mới) — trả `200` với số liệu rỗng (`0`/`[]`), KHÔNG phải lỗi.

**Admin Cấu hình hệ thống** — **CHƯA build**, xem `docs/plan/system-config-plan.md`:
- `GET|PUT /api/admin/config` — khi build xong, PUT có hiệu lực LIVE (agent-service đọc lại
  ngay lượt sau)

**SSE events từ `/ask`** (nguồn: `apps/agent-service/app/orchestrator/{nodes,runner}.py`):
| event | data | ý nghĩa |
|-------|------|---------|
| `status` | `{node, msg}` | mỗi node phát 1 lần: build_query/retrieve/synthesize/honest_answer/direct_response — **đây là chuỗi bước cho debug** |
| `token` | `{text}` | batch token câu trả lời |
| `citations` | `{citations:[...]}` | danh sách nguồn |
| `visualization` | `{visualization: VizPayload\|null}` | map+timeline |
| `clarification` | `{question}` | agent hỏi lại (ambiguous) |
| `regenerating` | `{}` | retry: clear token đã hiện |
| `blocked` | `{}` | guardrails chặn |
| `error` | `{code, message}` | lỗi sau khi mở stream |
| `done` | `{confidence, retrieval_mode, warnings, conversation_id, message_id}` | kết thúc; `message_id=null` nếu không lưu |
| `debug` | `{debug:{build_query:{standalone_query,route,mentioned_entities}, retrieve:{chunks,graph_context}}}` | ✅ đã code (`runner.py`), emit **NGAY TRƯỚC `done`, sau khi graph chạy xong hoàn toàn** — chỉ khi `debug=true` & role admin. Xem lưu ý realtime ở A3. |

**Types cần mirror sang TS** (`src/types/`):
- Chat: `User`, `Role`, `Conversation`, `Message` (=`MessageOut`: `id,role,content,clarification_needed,citations[],visualization,retrieval_mode,confidence,warnings[],created_at`), `Citation` (`chunk_id,source_file,chunk_index,start_line,end_line,heading_path[],quote`), `VisualizationPayload` (`markers[],timeline[],event_count,unplaced_count`), `MapMarker` (`event_id,label,summary,location,lat,lon,confidence,time_start?`), `TimelineItem` (`event_id,label,summary,time_start,time_end?,confidence,locations[],located`), `Document`, các `SseEvent` union.
- Module 5 (KB): `ChunkListItem` (`chunk_id,heading_path[],source_file?,start_line?,end_line?,preview`), `ChunkDetail` (`chunk_id,text,metadata,heading_path[],referencing_events:EventRef[]`), `EventRef` (`event_id,label,time_start?,time_end?,confidence`), `EventListItem` (`event_id,label,time_start?,time_end?,locations[],confidence`), `EventDetail` (`...EventListItem + summary,parent_event_norm?,source_chunk_ids[]`), `EntityListItem` (`name,norm_name,type?,description_count,source_chunk_count`), `EntityDetail` (`name,norm_name,type?,descriptions[],source_chunk_ids[],neighbors:EntityNeighbor[],edges:EntityEdge[]`), `EntityNeighbor` (`name?,norm_name?,type?`), `EntityEdge` (`source_name?,source_norm?,target_name?,target_norm?,keyword?,description,source_chunk_ids[]`).
- Module 4: `ConversationLogItem` (`id,title,user_email,user_name,message_count,created_at,updated_at`), `ConversationLogDetail` (`...+ messages:MessageLogItem[]`), `MessageLogItem` (`id,role,content,clarification_needed,citations[],visualization?,retrieval_mode,confidence?,warnings[],created_at,quality:MessageQuality`), `MessageQuality` (`retrieval_attempted,no_citation,low_confidence,clarification,has_warning` — tất cả bool), `QualitySummary` (`total_assistant_messages,retrieval_attempted_count,no_citation_count,low_confidence_count,clarification_count,warning_count`), `UserOut` (`id,email,name,role,is_active,question_quota?,created_at`), `UserCreate` (`email,name,role,password`), `UserUpdate` (`role?,is_active?,question_quota?`), `CostOverview` (`total_calls,total_tokens,total_prompt_tokens,total_completion_tokens,avg_tokens_per_call`), `DailyCost` (`day,calls,total_tokens`), `TaskCost` (`task,calls,total_tokens`), `TopUserCost` (`user_id,email,name,total_tokens,call_count`).

---

## Kiến trúc & cấu trúc thư mục (xây trên scaffold sẵn có)

```
src/
├── app/
│   ├── App.tsx              # route tree + RoleGuard
│   ├── providers.tsx        # QueryClientProvider, APIProvider (Google Maps), router
│   └── routes.tsx           # khai báo route user (/) vs admin (/admin/*)
├── api/
│   ├── client.ts            # fetch wrapper: base URL, gắn Bearer, ném {code,message}, 401→logout
│   ├── auth.ts  chat.ts  documents.ts  kb.ts
│   └── askStream.ts         # ⭐ SSE: fetch POST + ReadableStream, parse "event:/data:" → callbacks
├── types/                   # TS mirror Pydantic (xem §API contract)
├── store/
│   ├── authStore.ts         # token + user (persist localStorage), isAdmin selector
│   └── chatUiStore.ts       # vizPanelOpen, selectedEventId (link map↔timeline), debugOpen map
├── features/
│   ├── auth/                # LoginForm, useLogin, RoleGuard, RequireAuth
│   ├── chat/                # ChatPanel, MessageList, MessageBubble, Composer,
│   │                        #   CitationList, ClarificationPrompt, ConversationSidebar,
│   │                        #   useAskStream (hook gọi askStream + reducer event→UI state),
│   │                        #   DebugPanel (admin-only, collapsible dưới mỗi message)
│   ├── map/                 # EventMap (APIProvider+Map), EventMarker (đậm/nhạt theo confidence),
│   │                        #   MapEmptyState (honest fallback khi markers rỗng)
│   ├── timeline/            # TimelineBar (trục ngang zoom/pan, cluster, popover), link selectedEventId 2 chiều
│   ├── admin/               # DocumentTable, DocumentFormModal, StatusBadge
│   ├── kb/                  # Module 5 (read-only inspector):
│   │                        #   ChunkTable+ChunkDetail, EntityTable+EntityDetail (EgoGraph
│   │                        #   react-force-graph-2d), EventTable+EventDetail, KbSearchBar,
│   │                        #   ChunkRefLinks (điều hướng chéo qua chunk_id)
│   └── advanced/            # Module 4 (3 nhóm build thật + 1 stub "Sắp cập nhật"):
│                            #   ConversationLogTable+ConversationLogDetail+QualitySummaryCard,
│                            #   UserTable+UserCreateModal+UserEditModal,
│                            #   CostOverviewCards+CostByDayChart+CostByTaskChart+
│                            #   TopUsersTable+CostEstimateInput (dashboard Chi phí, recharts),
│                            #   ConfigTabStub ("Sắp cập nhật" — spec đã có ở system-config-plan.md)
├── components/              # Button, Input, Badge, Modal, Spinner, EmptyState (Tailwind+Radix)
└── pages/                   # LoginPage, AskPage, AdminLayout, AdminDocumentsPage,
                             #   AdminAdvancedPage, AdminKbPage (tabs Chunks/Graph/Timeline)
```

**Nguồn sự thật link map↔timeline**: `chatUiStore.selectedEventId`. Click marker hoặc timeline row đều set nó; cả hai component highlight theo. Tách store rõ ràng để unit-test (đây là điểm contribution ⭐).

---

## Pha A — Chi tiết build

### A1. Auth + Routing + Role gating
- `client.ts`: wrapper quanh `fetch`; tự gắn `Authorization: Bearer`; parse body lỗi `{code,message}`; `401` → clear authStore + redirect `/login`.
- `authStore`: lưu `{token, user}` (persist localStorage), selector `isAdmin = user.role === 'admin'`. Khi mở app, nếu có token → gọi `GET /me` xác thực; fail → logout.
- `routes.tsx`:
  - `/login` (public)
  - `/` → `AskPage` (RequireAuth, mọi role) — khu user
  - `/admin` → `AdminLayout` (RequireAuth + **RoleGuard admin**) chứa `/admin/documents`, `/admin/kb` (Module 5), `/admin/advanced`
  - `RoleGuard`: user chạm `/admin/*` → redirect `/` (FE chặn; BE đã chặn cứng `require_admin` + 403).
- Nav: user chỉ thấy link khu hỏi đáp; admin thấy thêm cụm "Quản trị" (Tài liệu, Kho tri thức, Nâng cao). Không render menu admin cho user.

### A2. Trang Hỏi đáp — Chat (user + admin)
- **Layout chat-first → split-screen** (theo frontend-scope): mặc định chat giữa; khi câu trả lời có sự kiện đủ data → bung split-screen (chat trái ~45–50%, map phải, timeline ngang đáy). Bung dựa trên `visualization` có `markers` hoặc `timeline` non-empty.
- **`useAskStream` hook**: gọi `askStream.ts`; nhận callback theo event:
  - `status` → đẩy vào `statusTrace` của message hiện tại (user: rút gọn thành spinner "đang suy nghĩ…"; admin: hiển thị đầy đủ trong DebugPanel).
  - `token` → append vào `content` (streaming text).
  - `regenerating` → reset `content` về "".
  - `citations` → set `citations`.
  - `visualization` → set `visualization` + mở viz panel nếu có data.
  - `clarification` → render `ClarificationPrompt` (ô trả lời nhanh; gửi tiếp giữ history).
  - `blocked` → thông báo bị chặn.
  - `error` → render khối lỗi đỏ (dùng `code/message`); phân biệt lỗi-trước-stream (HTTP 503/504/502 từ fetch) vs event `error`.
  - `debug` (admin) → set `message.debug`.
  - `done` → chốt `confidence/retrieval_mode/warnings`, gắn `message_id` từ event.
- **Multi-turn + sidebar** (backend đã có): `ConversationSidebar` list `GET /conversations`; "Cuộc trò chuyện mới" → `POST /conversations`; chọn phiên → `GET /conversations/{id}` load lại messages (kèm citations/visualization đã lưu). Câu hỏi gửi vào `/conversations/{id}/ask`.
- **UI nhỏ cần có** (frontend-scope §"UI nhỏ"): empty-state gợi ý 4 câu hỏi mẫu (README §5); trạng thái streaming; render confidence badge; phân biệt explicit/inferred.
- **Citations**: `CitationList` hiển thị `heading_path` + `source_file:start_line-end_line`; confidence của câu trả lời thành badge (`cao/vừa/thấp/không đủ dữ liệu`).
- **Chọn chế độ truy xuất (`RetrievalModeSelect`) — CHƯA build**: spec đầy đủ (dropdown "Mặc định hệ thống"/"Traditional RAG"/"GraphRAG"/"Hybrid" cạnh ô nhập câu hỏi, cho MỌI role, per-câu-hỏi) đã có sẵn ở `docs/plan/system-config-plan.md`. Build cùng đợt với tab Cấu hình hệ thống (C3), không phải bây giờ.

### A3. Debug view (admin-only) ⭐ yêu cầu mới
> Event `debug` đã code xong ở agent-service/backend (xem `backend-additions-plan.md` §1) —
> có thể nối thẳng, không cần chờ.
- **Gác hiển thị theo role**: chỉ render `DebugPanel` khi `authStore.isAdmin`. Request `/ask` của admin gửi `debug:true`; user gửi `debug:false` (và backend ép `False` nếu không phải admin — phòng thủ kép).
- **Vị trí**: panel **collapsible dưới mỗi message assistant** ("▸ Luồng xử lý"). Mặc định gập; admin bấm mở. Trạng thái mở/gập lưu per-message trong `chatUiStore.debugOpen`.
- **Nội dung panel** (gom từ stream của đúng lượt đó):
  - **Chuỗi bước (status trace)**: timeline các node + `msg` + thời điểm (build_query → retrieve → synthesize/honest_answer…), kèm trạng thái (đang chạy/xong). Realtime khi đang stream.
  - **Phân tích câu hỏi** (`debug.build_query`): `standalone_query` (câu đã viết lại), `route` (needs_retrieval/ambiguous/out_of_scope/smalltalk), `mentioned_entities` (entities seed).
  - **Retrieval** (`debug.retrieve`): số `chunks`, số `graph_context`; `retrieval_mode` (hybrid/none). Field `retrieval_backend` (mode đã resolve) sẽ xuất hiện SAU khi `system-config-plan.md` build xong — chưa có ở đợt này.
  - **Kết quả**: `confidence`, số citations, `warnings[]` (mỗi warning 1 dòng, ví dụ "build_query lỗi, fallback…", "visualization lỗi…").
  - **Visualization**: `event_count`, `unplaced_count`, số markers/timeline items.
- **Realtime**: panel cập nhật ngay khi event tới (status trace mọc dần); block "Phân tích/Retrieval/Kết quả" điền khi event `debug`/`done` về.
- **Ephemeral (MVP)**: xem lại lượt cũ (load từ DB) → panel chỉ có những gì đã persist (hiện chưa lưu debug → panel báo "không có dữ liệu debug cho lượt đã lưu"). Persist là việc sau (`backend-additions-plan.md` §1.3).

### A4. Trang Quản lý tài liệu (admin)
- `DocumentTable`: cột tên, loại, **StatusBadge** (draft/indexing/indexed/failed — màu khác nhau), số chunk, ngày tạo. Data qua TanStack Query `GET /api/admin/documents`.
- Thêm: `DocumentFormModal` → `POST` (MVP **chỉ metadata mock**, KHÔNG dropzone upload thật — theo frontend-scope §Module 3).
- Sửa trạng thái: `PATCH` (exclude_unset). Xóa: `DELETE` + confirm modal.
- Mọi mutation `invalidateQueries` để refresh list. Lỗi 404 → toast "Không tìm thấy tài liệu".

---

## Pha B — Map + Timeline (UI shell, data thưa)

- **EventMap**: `APIProvider` (key `VITE_GOOGLE_MAPS_API_KEY`) + `Map` + `AdvancedMarker`. **`.env.example`/`.env` hiện tại của frontend vẫn còn `VITE_MAP_TILE_URL=`** (leftover từ POC TrackAsia cũ, đã bỏ — xem CLAUDE.md §Map POC) **và CHƯA có `VITE_GOOGLE_MAPS_API_KEY`** — phải xóa biến cũ, thêm biến mới vào cả 2 file khi làm bước "Init project" (bước 0, xem "Thứ tự triển khai"). Center mặc định Việt Nam. Marker từ `visualization.markers`.
- **EventMarker**: render đậm/nhạt theo `confidence` (cao=đậm, thấp=nhạt — explicit vs inferred). Click → set `selectedEventId`.
- **TimelineBar** (đổi thiết kế 2026-07-03, thay Timeline/TimelineRow dọc cũ): thanh timeline **NGANG full-width dưới cùng AskPage** (kéo dưới cả sidebar + khung chat), tham khảo time-horizon.pages.dev. Trên trục chỉ có **icon + thời gian** (không hiện label/summary); click icon mới mở **popover chi tiết** (label, summary, locations, badge confidence, `located` → chấm liên kết map). Sự kiện sát nhau gom **cluster** (icon số đếm → popover danh sách). **Zoom bằng lăn chuột** tại con trỏ (tách cluster, tick tự chuyển năm→tháng), **kéo để pan**, double-click / nút "⟲ Toàn cảnh" reset. Chọn event → set `selectedEventId`. Hiện khi `visualization.timeline` non-empty, độc lập với panel map.
- **Link 2 chiều**: cả hai đọc `selectedEventId`; marker/row trùng `event_id` → highlight.
- **Honest fallback** (CLAUDE.md + viz schema):
  - `markers` rỗng (thực tế hiện tại do gazetteer hoãn) → ẩn map / hiện `MapEmptyState` ("Chưa có dữ liệu toạ độ cho sự kiện này"), vẫn render timeline.
  - thiếu thời gian → chỉ map; thiếu cả hai → không render (đếm `unplaced_count`, có thể chú thích "N sự kiện chưa đủ dữ liệu hiển thị").
  - không bấm/không có data → không bung viz panel.
- **Lưu ý vận hành**: vì gazetteer đang hoãn, demo hiện tại map gần như luôn ở empty-state; timeline là phần chạy thật. UI phải đẹp ở cả 2 trạng thái. Khi geocoding bật lại, marker tự xuất hiện không cần đổi FE.

---

## Pha A+ — Module 5 Trình xem kho tri thức (admin, read-only)

> Read endpoint `/api/admin/kb/*` đã code xong (xem `backend-additions-plan.md` §2 + API
> contract ở trên) — nối API thật ngay, không cần chờ.

`AdminKbPage` với 3 tab: **Chunks / Graph / Timeline**. Mục tiêu: xem trực tiếp dữ liệu đã index trên web thay vì mở Neo4j Browser / psql, và **điều hướng chéo bằng `chunk_id`** (khóa nối duy nhất giữa các store).

### Tab Chunks (`rag_chunks`)
- `ChunkTable`: cột `chunk_id`, `heading_path` (breadcrumb), `source_file:start_line-end_line`, preview text; phân trang (`limit/offset`), ô search (`text ILIKE` / lọc theo heading). Data: `GET /api/admin/kb/chunks`.
- `ChunkDetail`: full `text` + `metadata` JSONB (render đẹp: times/actors/locations/events), heading_path. Panel "Được tham chiếu bởi": phần **event** đã có sẵn trong response (`referencing_events[]`, backend tự join); phần **entity** phải gọi riêng `GET /api/admin/kb/entities?chunk_id=<id>` (proxy Neo4j qua agent-service) — 2 cơ chế khác nhau vì 2 store khác nhau, không lấy chung 1 field.

### Tab Graph (`:Entity` / `:REL`)
- `EntityTable`: list entity (name, type, số mô tả, số `source_chunk_ids`); lọc theo `type`, search theo `name`; phân trang. Data: `GET /api/admin/kb/entities` (backend proxy agent-service).
- `EntityDetail`: mô tả gộp + **`EgoGraph`** (`react-force-graph-2d`): node trung tâm + neighbor 1-hop, cạnh gắn `keyword`; click node → mở entity đó. Bảng quan hệ (source→keyword→target, descriptions). Link `source_chunk_ids` → tab Chunks.
  - **Kéo thả node**: dùng nguyên hành vi mặc định của `react-force-graph-2d` (force-directed, giống Neo4j Browser) — KHÔNG code thêm gì để phân biệt click/drag, thư viện tự nhận biết (giữ yên = click mở entity, kéo giữ = drag di chuyển node). **Chưa chốt** việc có ghim node tại chỗ sau khi thả hay để nó tiếp tục "trôi" theo simulation (mặc định) — quyết định để sau, không phải bây giờ.

### Tab Timeline (`timeline_events`)
- `EventTable`: list event (label, `time_start`–`time_end`, `locations`, `confidence` badge); lọc theo `confidence`, search theo label/summary; sort theo thời gian. Data: `GET /api/admin/kb/events`.
- `EventDetail`: summary đầy đủ, thời gian, locations, `parent_event_norm`, link `source_chunk_ids` → tab Chunks. (Gazetteer/lat-lon đang hoãn → không hiển thị toạ độ; note "chưa geocode".)

Toàn bộ **read-only**: chỉ GET, không nút sửa/xóa. Empty-state khi store rỗng (vd graph chưa index). Lỗi backend/agent (503/504 khi agent chết) → khối lỗi rõ ràng, không vỡ trang.

---

## Pha C1 — Module 4: 3 nhóm build thật

`AdminAdvancedPage` với tab điều hướng: **Hội thoại & chất lượng / Người dùng & quota /
Chi phí / Cấu hình** (3 tab đầu build thật ở đây; tab cuối là stub — xem Pha C3).
Endpoint tương ứng đã code xong: `backend-additions-plan.md` §3, §4 + API contract ở trên.

### Tab Hội thoại & chất lượng
- `LogsFilterBar`: lọc theo email user, khoảng ngày (`from_date`/`to_date`).
- `ConversationLogTable`: cột owner (email/name), title, `message_count`, `updated_at`;
  phân trang. Data: `GET /api/admin/logs/conversations`.
- `ConversationLogDetail`: mở 1 conversation → toàn bộ messages, mỗi message hiện cờ chất
  lượng do backend tính sẵn (confidence thấp/không đủ dữ liệu, thiếu citation, có
  clarification, có warning) dạng badge màu. Data: `GET /api/admin/logs/conversations/{id}`.
- `QualitySummaryCard`: tổng số message (`total_assistant_messages`), số confidence thấp, số
  clarification, số có warning — 4 số này chia trên `total_assistant_messages`. Riêng **số
  thiếu citation** hiển thị dạng `no_citation_count / retrieval_attempted_count` (KHÔNG chia
  cho `total_assistant_messages`) — vì message thuộc route clarify/smalltalk/out_of_scope
  vốn dĩ không có citation, không phải lỗi; chia nhầm mẫu số sẽ làm tỷ lệ % trông thấp giả
  tạo. Data: `GET /api/admin/logs/quality-summary`.
- Read-only hoàn toàn (không sửa/xóa hội thoại của user).

### Tab Người dùng & quota
- `UserTable`: cột email, name, role (badge admin/teacher), `is_active` (badge
  khóa/hoạt động), `question_quota` (số hoặc "không giới hạn"), ngày tạo. Data:
  `GET /api/admin/users`.
- `UserCreateModal`: tạo user mới (email/name/role/password). Email trùng → toast lỗi
  409 từ backend.
- `UserEditModal` (PATCH một phần — `exclude_unset`): đổi role, khóa/mở khóa
  (`is_active`), đặt `question_quota` (để trống = không giới hạn).
  - **Tự-khóa bị chặn ở backend** (409/400 tùy status code chọn) — FE cũng nên **disable**
    nút khóa trên chính hàng của admin đang đăng nhập để tránh click nhầm rồi nhận lỗi.
  - Khi khóa 1 user: hiện cảnh báo "Token hiện tại của user này sẽ bị từ chối ở lượt gọi
    API tiếp theo" (khóa có hiệu lực ngay, không cần user logout).
- Mutation xong → `invalidateQueries` refresh `UserTable`.

### Tab Chi phí ⭐ dashboard thật
> Chỉ track 2 lệnh gọi LLM online (`build_query`, `synthesize`) — KHÔNG có embedding (chạy
> model cục bộ, không tính phí theo token) và KHÔNG có chi phí indexing offline. Xem
> `backend-additions-plan.md` §Phần 4 cho phạm vi loại trừ đầy đủ.

- `CostFilterBar`: khoảng ngày (`from_date`/`to_date`), mặc định 7 ngày gần nhất.
- `CostOverviewCards` (hàng thẻ đầu tab, "sinh động" — số liệu tổng quan dễ nhìn ngay):
  tổng số lượt gọi LLM, tổng token, trung bình token/lượt gọi, tổng token prompt vs
  completion. Data: `GET /api/admin/cost/overview`.
- `CostByDayChart` (`recharts` bar/line): token theo ngày trong khoảng đã lọc — trục X ngày,
  trục Y **tổng `total_tokens`** (KHÔNG stack prompt/completion — `DailyCost` chỉ có
  `day,calls,total_tokens`, không có `prompt_tokens`/`completion_tokens` riêng theo ngày; số
  đó chỉ có ở `CostOverview` cho toàn khoảng, xem field ở API contract). Data:
  `GET /api/admin/cost/by-day`.
- `CostByTaskChart` (`recharts` bar/donut): so sánh **tổng `total_tokens`** giữa `build_query`
  (phân tích câu hỏi) và `synthesize` (soạn câu trả lời) — cho thấy tác vụ nào tốn nhất; cũng
  KHÔNG có breakdown prompt/completion theo task (`TaskCost` chỉ có `task,calls,total_tokens`).
  Data: `GET /api/admin/cost/by-task`.
- `TopUsersTable`: bảng top N user tốn token nhiều nhất (email, số lượt hỏi, tổng token);
  sort giảm dần theo `total_tokens`. Data: `GET /api/admin/cost/top-users?limit=10`.
- `CostEstimateInput`: ô nhập **"Giá ước tính ($/1K token)"** — tính CLIENT-SIDE, nhân trực
  tiếp với số token hiển thị ra số $ ước tính cạnh mỗi card/chart. **KHÔNG gửi lên backend,
  KHÔNG phải giá thật từ nhà cung cấp** — ghi chú rõ dưới ô input: "Chỉ là ước tính bạn tự
  nhập, không phản ánh giá thật của nhà cung cấp model."
- Toàn bộ **read-only** (chỉ GET, không sửa/xóa usage log).
- **Empty-state trước lần usage đầu tiên**: bảng `llm_usage` tạo lazy ở agent-service (chỉ có
  sau lệnh gọi LLM đầu tiên qua flow mới — xem `backend-additions-plan.md` §4.2), nên
  `GET /api/admin/cost/*` có thể trả toàn số liệu rỗng (`0`/`[]`) ngay cả khi API hoạt động
  bình thường. FE hiển thị empty-state ("Chưa có dữ liệu chi phí — hỏi thử vài câu để xem
  thống kê") cho case này, KHÔNG coi là lỗi.

### Tab Cấu hình hệ thống — xem Pha C3 (stub "Sắp cập nhật")

---

## Pha C3 — Module 4: Cấu hình hệ thống (đã có plan, chưa build — "Sắp cập nhật")

> Spec đầy đủ (retrieval mode selector 2 lớp + tinh chỉnh retrieval/synthesize +
> `ConfigForm` 3 nhóm + `RetrievalModeSelect` trong khung chat) đã viết sẵn ở
> `docs/plan/system-config-plan.md` — KHÔNG lặp lại ở đây. Build SAU KHI Pha C1 (3 nhóm build
> thật) + toàn bộ `backend-additions-plan.md` (Phần 1–4) xong, vì đây là phần đụng
> orchestrator đang chạy ổn định (nặng/rủi ro nhất trong Module 4).

MVP hiện tại: tab Cấu hình trong `AdminAdvancedPage` chỉ hiện thẻ **"Sắp cập nhật"** + mô tả
ngắn (dùng chữ khác "Sắp ra mắt" để phân biệt: tính năng này ĐÃ CÓ THIẾT KẾ đầy đủ, chỉ đang
chờ tới lượt build, không phải "chưa nghĩ tới"). Không render `RetrievalModeSelect` trong
`Composer` ở đợt này (xem A2 — đã note CHƯA build).

Khi tới lượt build: theo đúng `system-config-plan.md` — không cần thiết kế lại UI, chỉ cần
implement theo spec đã có (ConfigForm 3 nhóm: chế độ truy xuất mặc định / tinh chỉnh
retrieval / tinh chỉnh synthesize, cộng `RetrievalModeSelect` cho mọi user trong khung chat).

---

## Design system / styling

- Tailwind config theo tông đã chốt (frontend-scope §Hướng thiết kế): accent đỏ trầm `#A4161A`, nền be/kem ấm, heading serif + body sans-serif (học thuật, đáng tin).
- Primitives Radix (kiểu shadcn) cho Dialog/DropdownMenu/Tabs/Tooltip/Badge → form admin + modal nhanh, accessible.
- Component dùng chung trong `src/components/` để cả user/admin tái dùng.

---

## Testing

- **Unit (Vitest + React Testing Library)**:
  - `askStream` parser: feed chuỗi byte SSE giả → đúng event/data, xử lý `regenerating` reset, `debug`/`done`.
  - `chatUiStore`: set `selectedEventId` link map↔timeline.
  - `useAskStream` reducer: chuỗi event → state UI đúng (token append, citations, viz, clarification, error).
  - DebugPanel: render đúng status trace + debug fields; **ẩn hoàn toàn khi không phải admin**.
  - Honest fallback map/timeline theo markers/timeline rỗng.
  - RoleGuard: user vào `/admin/*` bị redirect.
  - Module 5: ChunkTable/EntityDetail/EventTable render từ data mock; điều hướng chéo qua `chunk_id`; empty-state khi store rỗng.
  - Module 4: `ConversationLogTable`/`QualitySummaryCard` render từ data mock + filter đúng tham số query; `UserEditModal` disable nút khóa trên hàng của chính admin đang đăng nhập; `CostOverviewCards`/`CostByDayChart`/`CostByTaskChart`/`TopUsersTable` render từ data mock; `CostEstimateInput` nhân đúng giá × token hoàn toàn client-side (không gọi API khi đổi giá).
- **Lint/format**: ESLint + Prettier + `tsc --noEmit`.

> Test `ConfigForm`/`RetrievalModeSelect` thuộc `system-config-plan.md` — chưa viết ở đợt
> này vì tính năng chưa build.

> Test cross-service (agent-service emit `debug`, backend ép `debug=False` cho user, read endpoint `/api/admin/kb/*`, logs/users/quota, cost usage logging + endpoint) thuộc `backend-additions-plan.md` §1.4 / §2.6 / §3 / §4.

---

## Verification (end-to-end)

1. Chạy backend (`uvicorn app.main:app --port 8000`) + agent-service (`:9000`); seed user demo (`admin@example.com/admin123`, `teacher@example.com/teacher123`).
2. `cd apps/frontend && npm run dev` (`:5173`); `.env` có `VITE_API_BASE_URL`, `VITE_GOOGLE_MAPS_API_KEY`.
3. **User flow**: login user (`teacher@example.com`) → hỏi 1 câu mẫu → thấy token stream, citations, confidence; câu có sự kiện → timeline hiện (map empty-state do gazetteer hoãn); **KHÔNG thấy DebugPanel** (chưa có `RetrievalModeSelect` ở đợt này — xem Pha C3); thử câu mập mờ → clarification; sidebar tạo/đổi phiên giữ history.
4. **Admin flow**: login admin → vào khu hỏi đáp (như user) → mỗi câu trả lời có panel "▸ Luồng xử lý"; mở ra thấy chuỗi node + standalone_query + route + entities + số chunk/graph + confidence + warnings, cập nhật realtime khi stream → khu `/admin/documents` thêm/sửa/xóa tài liệu mock, StatusBadge đúng.
5. **Module 5 (KB Inspector)**: `/admin/kb` → tab Chunks duyệt/search `rag_chunks`, mở chi tiết thấy full text + metadata; tab Graph list entity, mở chi tiết thấy ego-graph 1-hop; tab Timeline list event; điều hướng chéo chunk↔entity↔event qua `chunk_id` hoạt động; store rỗng → empty-state.
6. **Module 4 — Hội thoại & chất lượng**: `/admin/advanced` tab đầu → lọc theo email/khoảng ngày, mở 1 conversation thấy cờ chất lượng đúng trên từng message, `QualitySummaryCard` đếm khớp.
7. **Module 4 — Người dùng & quota**: tạo user mới → login được ngay; khóa user đó (`is_active=false`) → user đó gọi API bất kỳ nhận 403 `account_locked` dù token còn hạn; đặt `question_quota=1` cho 1 user → hỏi câu thứ 2 trong ngày nhận 429 `quota_exceeded`; admin không tự khóa được chính mình.
8. **Module 4 — Chi phí**: `/admin/advanced` tab Chi phí → `CostOverviewCards` hiện đúng tổng lượt gọi/tổng token; hỏi thêm vài câu ở khu chat → refresh tab thấy số liệu tăng theo (`build_query` + `synthesize` mỗi câu); `CostByDayChart`/`CostByTaskChart` render đúng theo `from_date`/`to_date` đã lọc; `TopUsersTable` sort đúng theo `total_tokens`; nhập giá ở `CostEstimateInput` → số $ ước tính cập nhật ngay, không gọi API. Tab Cấu hình hệ thống hiện "Sắp cập nhật" (không phải form thật) — verification đầy đủ cho Cấu hình chuyển sang `system-config-plan.md` khi tới lượt build.
9. **Gating**: user mở thẳng URL `/admin/documents`, `/admin/kb`, hoặc `/admin/advanced` → bị redirect; gọi API admin (gồm `/api/admin/kb/*`, `/api/admin/logs/*`, `/api/admin/users`) → 403. User ép `debug:true` trong request → backend trả về không có event `debug`.
10. `npm run test` + `tsc --noEmit` xanh; lint sạch.

---

## Thứ tự triển khai đề xuất (frontend)

> Backend/agent-service cho Phần 1–4 (`backend-additions-plan.md`) **đã code xong toàn bộ**,
> nên thứ tự dưới đây không còn ràng buộc "chờ backend" nào — chỉ là thứ tự triển khai FE hợp
> lý (nền tảng trước, tính năng rủi ro thấp trước).

0. **Init project** (chưa có, phải làm trước bước 1): tạo `package.json` (Vite + React + TS
   template), `vite.config.ts`, `tsconfig.json`/`tsconfig.node.json`, `index.html`,
   `src/main.tsx`; cài lại/đối chiếu deps trong `node_modules` sẵn có (`react`, `react-dom`,
   `react-router-dom`, `vite` đã có — thêm các gói còn thiếu: TanStack Query, Zustand,
   Tailwind, Radix, `@vis.gl/react-google-maps`, `react-force-graph-2d`, `recharts`); đổi
   `.env`/`.env.example` (xem A2 lưu ý dưới) trước khi `npm run dev` chạy được.
1. Nền: tooling (Tailwind/Radix/TanStack/Zustand/vis.gl), `client.ts`, types, authStore, routing + guards, LoginPage.
2. Chat user: `askStream`, `useAskStream`, ChatPanel + Composer + MessageList + citations + clarification + empty-state.
3. Multi-turn sidebar (conversations CRUD + load lại).
4. DebugPanel admin (API đã sẵn sàng — event `debug`, xem `backend-additions-plan.md` §1).
5. Map + Timeline + honest fallback + link `event_id`.
6. Admin documents (table + CRUD mock).
7. Module 5 KB Inspector (API đã sẵn sàng — `backend-additions-plan.md` §2): tab Chunks/Graph/Timeline + điều hướng chéo.
8. Module 4 — 3 nhóm build thật (API đã sẵn sàng — `backend-additions-plan.md`
   §3, §4), theo thứ tự rủi ro tăng dần: tab Hội thoại & chất lượng (read-only, an toàn
   nhất) → tab Người dùng & quota (đụng đăng nhập/khóa tài khoản, test kỹ) → tab Chi phí
   (thêm dependency `recharts`, dựng `CostOverviewCards`/`CostByDayChart`/
   `CostByTaskChart`/`TopUsersTable`/`CostEstimateInput`). Tab Cấu hình hệ thống chỉ hiện
   stub "Sắp cập nhật" + nav admin.
9. Test + verify + polish design system.
10. **(Đợt sau, plan riêng)** Cấu hình hệ thống + `RetrievalModeSelect` — theo
    `docs/plan/system-config-plan.md`, làm sau khi bước 1–9 xong và backend
    `system-config-plan.md` đã build.
