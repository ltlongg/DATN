# Plan Backend Additions — Bổ sung API cho Frontend

## Context

Frontend (xem `docs/plan/frontend-plan.md`) cần tiêu thụ API thật cho cả 2 role (user +
admin). Backend + agent-service **đã build gần đủ**, nhưng còn **3 nhóm khoảng trống** phải
lấp trước/song song khi dựng frontend:

1. **Debug streaming** — luồng `/ask` chưa pipe `state["debug"]` qua SSE (chỉ đường
   non-stream đính vào `AskResponse.debug`). Debug view admin cần event này.
2. **Read endpoints cho Module 5** (KB Inspector) — data đã có (Postgres `rag_chunks` +
   `timeline_events`, Neo4j `:Entity`/`:REL`) nhưng **chưa expose** qua HTTP.
3. **Module 4 (admin nâng cao) — 3/4 nhóm build THẬT ngay** (Hội thoại & chất lượng, Người
   dùng & quota, Chi phí). Nhóm **Cấu hình hệ thống** đã **tách sang plan riêng**
   `docs/plan/system-config-plan.md` (retrieval mode selector + tinh chỉnh
   retrieval/synthesize, áp dụng LIVE) — nặng/rủi ro nhất trong Module 4 (đụng cả
   orchestrator đang chạy ổn định), làm SAU KHI Phần 1, 2, 3, 4 trong file này xong. Không
   nằm trong phạm vi file này.

> **Thuật ngữ**: role không-phải-admin gọi là **"user"** ở mô tả; **giá trị literal trong
> code vẫn là `teacher`** (`Role = admin|teacher`). Giữ nguyên `teacher` ở mọi chỗ là giá
> trị code.

Nguyên tắc CLAUDE.md áp dụng: chunk/event ở Postgres → **backend query trực tiếp** (`psycopg`
+ `app/core/db.py::connection()`, pattern `models/document.py`); graph ở Neo4j → backend
**không có driver** nên **proxy sang agent-service** (agent có `app/core/neo4j.py` +
`graph_store.py`). Mọi endpoint admin **gác cứng `require_admin`**.

> **Bắt buộc: mọi model file MỚI dùng `connection()` phải thêm vào
> `tests/conftest.py::_DB_MODULES`**. Fixture `db_conn` patch `connection` theo TÊN MODULE
> (hiện chỉ có `app.core.db`, `app.models.user`, `app.models.conversation`,
> `app.models.document` — xem `conftest.py:28`); patch theo tên nghĩa là module KHÔNG có
> trong danh sách vẫn gọi `connection()` THẬT, mở connection riêng ngoài transaction rollback
> của test. Hệ quả nếu quên: test đọc dữ liệu do fixture khác insert trong cùng transaction sẽ
> thấy rỗng (transaction khác nhau không thấy uncommitted data của nhau — false negative);
> nếu model đó có ghi (INSERT/UPDATE), sẽ **ghi thật vào Postgres remote dev dùng chung**,
> không rollback được. Plan này thêm `app/models/inspect.py` (Phần 2), `app/models/logs.py`
> (Phần 3.1), `app/models/cost.py` (Phần 4) — **cả 3 đều phải thêm vào `_DB_MODULES`**;
> `system-config-plan.md` thêm `app/models/config.py` — cũng phải thêm tương tự (ghi ở file
> đó).

---

## Phần 1 — Debug streaming (bắt buộc cho Pha A của frontend)

Debug "đầy đủ" cần `state["debug"]` lọt qua đường streaming. Hiện `run_ask_stream` KHÔNG
phát debug. 3 thay đổi:

### 1.1 agent-service — emit event `debug`
`apps/agent-service/app/orchestrator/runner.py::run_ask_stream`: sau khi graph chạy xong,
nếu `request.debug` thì `yield _sse("debug", {"debug": final_state.get("debug", {})})`
**trước** event `done`.
- `state["debug"]` đã tích lũy `build_query` + `retrieve` nhờ reducer `_merge_debug` trong
  `state.py` (đã verify).
- Shape: `{debug: {build_query: {standalone_query, route, mentioned_entities},
  retrieve: {chunks, graph_context}}}`.

**Đánh đổi đã chốt — "gom debug rồi bắn 1 lần ở cuối"** (không emit per-node):
- **Dữ liệu debug có sớm, nhưng gửi muộn.** `debug.build_query` được ghi ngay ở node đầu,
  `debug.retrieve` ở node retrieve — nhưng `run_ask_stream` chỉ đọc `final_state["debug"]`
  **sau khi `graph.ainvoke` chạy xong** (không đọc `state["debug"]` giữa chừng). Vì vòng lặp
  stream đọc queue của `emitter` và `yield` realtime, event `debug` chỉ được bắn **sau khi
  toàn bộ `status`/`token`/`citations`/`visualization` đã stream hết**, ngay trước `done`.
- **Hệ quả trên UI**: trong `DebugPanel`, phần **status trace** mọc realtime từ đầu; nhưng
  block **"Phân tích câu hỏi" + "Retrieval"** (standalone_query/route/entities/số chunk/graph)
  **trống cho tới sát cuối** — chỉ điền khi event `debug` về, tức sau khi answer đã gõ xong.
  Đây là hành vi CỐ Ý, không phải panel treo/lỗi. FE nên hiện placeholder "đang xử lý…" cho
  block này tới khi có event `debug`.
- **Lý do chọn**: đơn giản hơn nhiều so với emit-per-node (không phải gác `request.debug` ở
  tầng node, không truyền cờ debug vào state/config). Đủ cho MVP.
- **Option nâng cấp (KHÔNG làm bây giờ)**: muốn debug realtime từng node (standalone_query
  hiện ngay khi build_query xong) thì cho node tự `await emitter.emit("debug", {...})` thay vì
  chỉ gom vào `state["debug"]`; đổi lại phải truyền cờ `request.debug` xuống node. Ghi lại
  đây làm hướng mở rộng nếu sau này thấy cần.

### 1.2 backend — gác role server-side
`apps/backend/app/api/chat.py::ask`: chỉ honor `debug=True` khi `user.role == "admin"`; user
gửi `debug=true` vẫn bị **ép `False`** (gác cổng server-side, phòng thủ kép với FE).
- `_proxy_stream` đã forward mọi event ≠ `done` nguyên văn → event `debug` tự xuống frontend,
  **không cần sửa thêm** đường proxy.
- `SseCollector.feed` bỏ qua event lạ → không vỡ khi gặp `debug`.

### 1.3 (Tùy chọn, để sau) Persist debug
Xem lại conversation cũ cần lưu debug: thêm cột `messages.debug JSONB` + `MessageOut.debug` +
`SseCollector` bắt event `debug`. **MVP để debug ephemeral** (chỉ thấy lúc stream trực tiếp;
xem lại lượt cũ → panel trống). Đây là quyết định có chủ đích.

### 1.4 Test
- agent-service: `run_ask_stream` phát `debug` khi `request.debug=True` (mock graph); KHÔNG
  phát khi `False`.
- backend: `ask` ép `debug=False` cho user (role `teacher`); giữ `True` cho admin.

---

## Phần 2 — Read endpoints cho Module 5 (KB Inspector, read-only)

Data đã có nhưng chưa expose. Mọi endpoint **read-only + gác `require_admin`**. Prefix
`/api/admin/kb`.

### 2.1 backend — chunks / events (psycopg direct)
Thêm `app/models/inspect.py` (mirror `models/document.py`, hàm SYNC gọi qua
`anyio.to_thread`) + router `app/api/inspect.py`:

**Chunks** (`rag_chunks`)
- `GET /api/admin/kb/chunks?q&heading&limit&offset` → list: `chunk_id`, `heading_path`,
  `source_file`, `start_line`, `end_line`, preview text (cắt ngắn); phân trang + tổng count.
  Search: `text ILIKE %q%`; lọc `heading_path` (GIN nếu có).
- `GET /api/admin/kb/chunks/{chunk_id}` → full `text` + `metadata` JSONB + `heading_path`.
  Kèm **"được tham chiếu bởi"** — cơ chế KHÁC NHAU cho event và entity (2 store khác nhau):
  - **Event** (`timeline_events`, Postgres): backend tự query trực tiếp
    `WHERE source_chunk_ids @> ARRAY[chunk_id]` trong `app/models/inspect.py` — KHÔNG cần
    gọi agent-service, dữ liệu nằm sẵn trong Postgres backend đã có driver.
  - **Entity** (`:Entity`, Neo4j): PHẢI qua agent-service vì Neo4j không có driver ở backend
    — dùng endpoint `GET /kb/entities?chunk_id=...` mới (xem 2.2), proxy qua `agent_client`
    (xem 2.3). Đây là phần **trước đây plan CHƯA thiết kế** (chỉ có filter theo `q`/`type`,
    không có `chunk_id`) — đã bổ sung.

**Events** (`timeline_events`)
- `GET /api/admin/kb/events?q&confidence&limit&offset` → list: `event_id`, `label`,
  `time_start`, `time_end`, `locations`, `confidence`; phân trang. Lọc `confidence`, search
  label/summary; sort `time_start` (đã có index).
- `GET /api/admin/kb/events/{event_id}` → chi tiết đầy đủ + `summary`, `parent_event_norm`,
  `source_chunk_ids`. (Gazetteer hoãn → **không trả lat/lon**.)

### 2.2 agent-service — graph read
Thêm hàm read trong `graph_store.py`:
- `list_entities(type?, q?, chunk_id?, limit, offset)` + `count_entities(...)` —
  list/paginate `:Entity` theo `type`, search theo `name`, **và lọc theo `chunk_id`** (Cypher
  `WHERE $chunk_id IS NULL OR $chunk_id IN e.source_chunk_ids` — `source_chunk_ids` đã có
  sẵn trên node `:Entity`, xem `graph_store.py::_MERGE_ENTITIES`). Field `chunk_id` mới này
  là phần bổ sung để phục vụ "được tham chiếu bởi" ở chunk detail (2.1) — 2 tham số filter
  (`q`/`type` vs `chunk_id`) dùng độc lập, không bắt buộc kết hợp.
- `get_entity(norm_name)` + neighbors 1-hop (tái dùng ý tưởng `_EXPAND_SEED`) → ego-graph
  (node trung tâm + neighbor + edges gắn `keyword`).

Thêm endpoint trong `api/`:
- `GET /kb/entities?q&type&chunk_id&limit&offset` → list entity (`name`, `type`, số mô tả, số
  `source_chunk_ids`). Gọi với `chunk_id=<id>` (không kèm `q`/`type`) → trả đúng danh sách
  entity tham chiếu chunk đó, dùng cho panel "được tham chiếu bởi".
- `GET /kb/entities/{norm_name}` → ego-graph: node + edges 1-hop + bảng quan hệ
  (source→keyword→target, descriptions) + `source_chunk_ids`.

### 2.3 backend — proxy graph qua agent_client
Mở rộng nhẹ `services/agent_client.py`; router `inspect.py` thêm:
- `GET /api/admin/kb/entities?q&type&chunk_id&limit&offset` → proxy `GET /kb/entities`
  (forward nguyên `chunk_id` nếu có).
- `GET /api/admin/kb/entities/{norm_name}` → proxy `GET /kb/entities/{norm_name}`.

Lỗi agent chết → map 503/504/502 như pattern `agent_client` hiện có.

### 2.4 Điều hướng chéo bằng `chunk_id`
`chunk_id` là khóa nối duy nhất (Postgres PK ↔ Qdrant payload ↔ Neo4j `source_chunk_ids` ↔
`timeline_events.source_chunk_ids`). Endpoint phải hỗ trợ 2 chiều — cơ chế khác nhau theo
store (đã cụ thể hóa ở 2.1/2.2, không còn chung chung):
- **Chi tiết chunk → liệt kê event/entity tham chiếu nó**: event dùng SQL filter trực tiếp
  trên `timeline_events` (backend tự query, 2.1); entity dùng `GET /kb/entities?chunk_id=...`
  (agent-service, 2.2/2.3).
- **Chi tiết entity/event → trả `source_chunk_ids`** để FE link ngược tới chunk nguồn (đã có
  sẵn trong response `/kb/entities/{norm_name}` và `/api/admin/kb/events/{event_id}`).

Đây là giá trị chính của inspector.

### 2.5 Read-only tuyệt đối
KHÔNG endpoint ghi/xóa/merge. Quản lý (xóa/re-index/merge alias) là giai đoạn sau, cần logic
đồng bộ Postgres↔Qdrant↔Neo4j — ghi rõ là việc sau.

### 2.6 Test
> **`tests/conftest.py::_DB_MODULES` phải thêm `"app.models.inspect"`** (xem lưu ý chung ở
> đầu file) — nếu không, `/chunks`/`/events` test sẽ không thấy chunk/event fixture insert
> qua `db_conn` (transaction khác), hoặc tệ hơn ghi thật vào Postgres remote.

- backend: `/api/admin/kb/chunks`, `/chunks/{id}`, `/events`, `/events/{id}` trả đúng shape
  + phân trang + gác `require_admin` (user 403); `/chunks/{id}` panel "được tham chiếu bởi"
  trả đúng event khớp `source_chunk_ids @> ARRAY[chunk_id]`.
- backend: `/api/admin/kb/entities*` proxy đúng (mock agent qua `httpx.MockTransport`),
  forward đúng tham số `chunk_id` khi có.
- agent-service: `graph_store::list_entities` với `chunk_id=X` trả đúng entity có `X` trong
  `source_chunk_ids`, KHÔNG trả entity không liên quan; endpoint `/kb/entities*` trả đúng
  shape, empty-state khi graph rỗng.

---

## Phần 3 — Module 4 Admin nâng cao (build THẬT — 2/4 nhóm ở đây, +1 nhóm ở Phần 4)

Quyết định 2026-07-01: build thật ngay **2 nhóm** trong mục này (Hội thoại & chất lượng ·
Người dùng & quota); nhóm **Chi phí** cũng build thật nhưng tách thành Phần 4 riêng (đụng
orchestrator, khác nhóm 3.1/3.2 vốn chỉ đụng backend). Nhóm **Cấu hình hệ thống** đã tách
hẳn sang `docs/plan/system-config-plan.md` — làm sau khi Phần 1, 2, 3, 4 xong.

### 3.1 Hội thoại & chất lượng (read-only, KHÔNG cần bảng mới)

Toàn bộ dữ liệu đã có sẵn trong `conversations`/`messages` (cột `confidence`, `citations`,
`clarification_needed`, `warnings` đã lưu mỗi message). Chất lượng là **suy ra**, không lưu
cờ riêng.

- **backend — `app/models/logs.py`** (mới, không đụng `models/conversation.py` hiện có):
  - `list_conversations_admin(user_email?, from_date?, to_date?, limit, offset)` → JOIN
    `conversations c` với `users u` (lấy `user_email`/`user_name`) + subquery đếm
    `message_count`; lọc theo `updated_at` range + email chính xác; sort `updated_at DESC`.
  - `get_conversation_detail_admin(conversation_id)` → conversation + owner + toàn bộ
    `messages` (tái dùng `_MSG_COLS` kiểu `models/conversation.py`).
  - `list_quality_rows(from_date?, to_date?)` → trả các cột thô (`confidence`, `citations`,
    `clarification_needed`, `warnings`, **`retrieval_mode`**, `created_at`) của message
    `role='assistant'` trong khoảng thời gian — KHÔNG tính toán trong SQL. Thêm cột
    `retrieval_mode` (trước đây thiếu) vì cần nó để định nghĩa đúng mẫu số cho `no_citation`
    (xem ngay dưới).
- **backend — `app/services/quality_service.py`** (mới, hàm THUẦN không I/O — cùng idiom với
  `conversation_service.py::derive_title`): `compute_quality_summary(rows) -> QualitySummary`.
  **Mẫu số KHÁC NHAU theo field** (tránh đếm sai — `clarify()`/`direct_response`/route
  `out_of_scope` không qua `retrieve()` nên `retrieval_mode` giữ `"none"` mặc định và
  `citations=[]` là BÌNH THƯỜNG, không phải lỗi; xác nhận qua `nodes.py::retrieve()` set
  `retrieval_mode="hybrid"` — chỉ node này set — và `clarify()` set cứng `"none"`):
  - `total_assistant_messages` — đếm trên TOÀN BỘ `rows` (mẫu số cho `has_clarification`,
    `has_warning` — 2 field này CÓ Ý NGHĨA bất kể route nào, không cần lọc).
  - `retrieval_attempted_count` — đếm subset `retrieval_mode != "none"` (**mẫu số cho
    `no_citation`**, KHÔNG PHẢI `total_assistant_messages`).
  - `no_citation_count` — đếm `citations` rỗng **CHỈ trong subset `retrieval_mode !=
    "none"`** (message đã thử retrieval mà vẫn không có citation hợp lệ mới là tín hiệu đáng
    chú ý; message thuộc route clarify/smalltalk/out_of_scope vốn dĩ không có citation, KHÔNG
    tính vào đây).
  - `low_confidence_count` — confidence ∈ {"thấp","không đủ dữ liệu"}, đếm trên toàn bộ
    `rows` (không bị ảnh hưởng bởi bug này: confidence=`None` ở các route không retrieval
    không khớp 2 giá trị trên nên không bị đếm nhầm — vẫn ghi rõ ở đây để không mơ hồ).
  - `clarification_count` — `clarification_needed=True`, đếm trên toàn bộ `rows`.
  - `warning_count` — `warnings` non-empty, đếm trên toàn bộ `rows`.
  Tách thuần để unit-test không cần DB — test phải có ca message `retrieval_mode="none"` +
  `citations=[]` để verify KHÔNG bị tính vào `no_citation_count`.
- **backend — `app/schemas/logs.py`** + **`app/api/logs.py`** (prefix `/api/admin/logs`,
  `require_admin`):
  - `GET /api/admin/logs/conversations?user_email&from_date&to_date&limit&offset`
  - `GET /api/admin/logs/conversations/{id}` → chi tiết + mỗi message kèm cờ chất lượng
    (tính bằng hàm thuần ở trên, không lưu thêm cột).
  - `GET /api/admin/logs/quality-summary?from_date&to_date` → tổng hợp đếm, trả cả
    `retrieval_attempted_count` (để FE hiển thị đúng tỷ lệ `no_citation_count /
    retrieval_attempted_count`, KHÔNG chia cho `total_assistant_messages` — tránh tỷ lệ % bị
    hạ thấp giả tạo do lẫn message không cần citation).
- Đăng ký router trong `main.py`. **`tests/conftest.py::_DB_MODULES` phải thêm
  `"app.models.logs"`** (xem lưu ý chung ở đầu file) — endpoint test insert conversation/
  message qua `db_conn` rồi `list_conversations_admin`/`list_quality_rows` đọc lại, nếu
  `app.models.logs` không patch thì đọc bằng connection thật, không thấy data vừa insert
  trong transaction test. Test: filter đúng, phân trang, `require_admin` chặn `teacher`
  (403); `compute_quality_summary` test thuần bằng dict giả gồm CẢ message
  `retrieval_mode="hybrid"` lẫn `"none"` — verify `no_citation_count` chỉ đếm subset hybrid,
  `total_assistant_messages`/`clarification_count`/`warning_count` đếm đủ toàn bộ.

### 3.2 Người dùng & quota

**Sửa thẳng bảng `users`, KHÔNG migration** — quyết định 2026-07-01: đang dev, chưa có user
thật (chỉ 2 seed demo `admin@example.com`/`teacher@example.com`), nên sửa thẳng câu
`CREATE TABLE IF NOT EXISTS users (...)` hiện có trong `app/core/db.py::SCHEMA_STATEMENTS`
để thêm 2 cột mới NGAY TỪ ĐẦU — KHÔNG cần `ALTER TABLE ... ADD COLUMN` migration lằng nhằng:
```sql
CREATE TABLE IF NOT EXISTS users (
    id             UUID PRIMARY KEY,
    email          TEXT UNIQUE NOT NULL,
    name           TEXT NOT NULL,
    role           TEXT NOT NULL,
    password_hash  TEXT NOT NULL,
    is_active      BOOLEAN NOT NULL DEFAULT true,
    question_quota INTEGER,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
```
`question_quota IS NULL` = không giới hạn.

> **Nguyên tắc áp dụng dev-only này**: CHỈ cho bảng backend tự quản (`users`/`conversations`/
> `messages`/`documents` — rỗng/dễ seed lại). **TUYỆT ĐỐI KHÔNG** áp dụng cho bảng tốn nhiều
> thời gian/tiền API để dựng lại (`rag_chunks`, `timeline_events`, Qdrant collection, Neo4j
> graph — dữ liệu đã index từ LLM calls thật) — mấy bảng đó vẫn phải migrate/giữ nguyên, không
> được drop/tạo lại.

**Thao tác khi implement** (vì `CREATE TABLE IF NOT EXISTS` không tự thêm cột vào bảng ĐÃ tồn
tại — phải drop trước để statement mới thật sự áp dụng):
1. **Drop theo đúng thứ tự phụ thuộc, KHÔNG dùng `CASCADE`** — con trước, cha sau:
   ```sql
   DROP TABLE IF EXISTS messages;
   DROP TABLE IF EXISTS conversations;
   DROP TABLE IF EXISTS users;
   ```
   **Lý do KHÔNG dùng `DROP TABLE users CASCADE`**: `ON DELETE CASCADE` trên
   `conversations.user_id REFERENCES users(id)` chỉ là cascade cấp **row** (áp dụng khi
   `DELETE FROM users`), khác hẳn `DROP TABLE ... CASCADE` — cascade cấp **DDL**. Với DDL
   cascade, Postgres chỉ tự drop **constraint** phụ thuộc (ở đây là chính FK đó), KHÔNG drop
   bảng `conversations`/`messages`. Kết quả nếu lỡ dùng `CASCADE`: `users` bị xóa, nhưng
   `conversations`/`messages` còn nguyên — mồ côi, mất luôn ràng buộc FK. Drop theo thứ tự
   tường minh ở trên tránh hẳn vấn đề này, không cần `CASCADE`.
2. Thay hẳn statement `users` cũ trong `SCHEMA_STATEMENTS` bằng bản có 2 cột mới ở trên (sửa
   tại chỗ, không thêm statement `ALTER` riêng).
3. Chạy lại `python scripts/init_db.py` (tạo `users`/`conversations`/`messages` mới) rồi
   `python scripts/seed_users.py` (seed lại 2 user demo).

- **`app/models/user.py`**: `User` thêm `is_active: bool`, `question_quota: int | None`; mở
  rộng `_SELECT`/`_row_to_user`; thêm `list_users()`, `update_user(user_id, fields: dict)`
  (mirror `update_document` — PATCH một phần).
- **`app/models/conversation.py`**: thêm `count_user_messages_today(user_id) -> int` —
  `SELECT count(*) FROM messages m JOIN conversations c ON c.id = m.conversation_id WHERE
  c.user_id = %s AND m.role = 'user' AND m.created_at >= date_trunc('day', now())` (mốc thời
  gian tính ở phía Postgres, không truyền datetime từ Python — tránh lệch múi giờ app/DB).
- **`app/api/deps.py::get_current_user`**: sau khi nạp `user`, nếu `not user.is_active` →
  `AppError(403, "account_locked", "Tài khoản đã bị khóa.")`. Kiểm tra ở MỌI request đã có
  token (không chỉ những request tạo mới token) → khóa có hiệu lực ngay cả với token còn hạn.
- **`app/api/auth.py::login`**: **thêm check `is_active` NGAY TRONG login**, sau
  `verify_password` thành công, TRƯỚC `create_access_token` — nếu `not user.is_active` →
  `AppError(403, "account_locked", "Tài khoản đã bị khóa.")`. **Lý do bắt buộc**: `login`
  không đi qua `get_current_user` (không có token lúc gọi `/login`, tự làm
  `get_user_by_email` → `verify_password` → `create_access_token` độc lập) — nếu chỉ check
  ở `get_current_user`, user bị khóa vẫn login thành công và nhận token mới (dù request kế
  tiếp sẽ bị 403 ngay). Cần check ở CẢ HAI chỗ: `login` (chặn cấp token mới cho tài khoản đã
  khóa) và `get_current_user` (chặn token cũ còn hạn dùng tiếp).
- **`app/api/chat.py::ask`**: thêm dependency `user: User = Depends(get_current_user)`
  (cache theo request, không tốn thêm query vì `get_owned_conversation` đã gọi cùng
  dependency). **Check quota TRƯỚC bước lưu user message** (bước 3 trong `ask()` — hiện tại
  `conv_repo.add_message(conv.id, "user", body.question)` — KHÔNG PHẢI chỉ "trước khi mở
  stream agent" ở bước 5). **Off-by-one nếu đặt sai chỗ**: `count_user_messages_today` đếm
  cả message vừa lưu ở bước 3; nếu check chạy SAU bước 3 (vd đặt ngay trước bước 5), với
  `question_quota=1` thì câu hỏi ĐẦU TIÊN đã tự đẩy count lên 1 → bị chặn nhầm ngay từ câu
  đầu thay vì câu thứ 2. Thứ tự đúng: kiểm tra
  `user.question_quota is not None and count_user_messages_today(user.id) >=
  user.question_quota` **NGAY ĐẦU `ask()`, trước khi gọi `add_message` cho câu hỏi hiện
  tại** → nếu vượt, `AppError(429, "quota_exceeded", f"Bạn đã dùng hết quota
  {user.question_quota} câu hỏi hôm nay.")` (chưa lưu message, chưa mở stream).
- **`app/schemas/user.py`** (mới): `UserOut`, `UserCreate` (email/name/role/password),
  `UserUpdate` (role?/is_active?/question_quota?, `exclude_unset`).
- **`app/api/users.py`** (mới, prefix `/api/admin/users`, `require_admin`):
  - `GET /api/admin/users` → `list_users()`.
  - `POST /api/admin/users` → tạo user mới (hash password, reuse `create_user`); email
    trùng → bắt `psycopg.errors.UniqueViolation` → `AppError(409, "conflict", ...)`.
  - `PATCH /api/admin/users/{id}` → đổi role/is_active/question_quota. **Guard tự khóa**:
    chặn admin tự đặt `is_active=False` cho chính mình (tránh khóa nhầm mất quyền truy cập).
- Đăng ký router trong `main.py`. Test: CRUD, `require_admin` chặn teacher, email trùng 409,
  tự-khóa bị chặn; tài khoản bị khóa → `POST /api/auth/login` trả 403 `account_locked` (KHÔNG
  cấp token mới), và token cũ còn hạn của tài khoản đó cũng nhận 403 ở MỌI endpoint qua
  `get_current_user`; quota: đặt `question_quota=1` → **câu hỏi đầu tiên trong ngày PHẢI
  thành công** (test regression cho off-by-one), câu hỏi thứ 2 mới nhận 429, và message của
  câu bị chặn KHÔNG được lưu vào `messages` (verify `add_message` không chạy khi quota vượt).

### 3.3 Cấu hình hệ thống — ĐÃ TÁCH sang plan riêng

Xem `docs/plan/system-config-plan.md` — toàn bộ thiết kế bảng `system_config`, wiring
retrieval/synthesize, override per-câu-hỏi (`AskRequest.retrieval_backend`), test, và spec
frontend tương ứng. KHÔNG lặp lại nội dung ở đây để tránh 2 nguồn sự thật; sửa gì thì sửa ở
file đó. Thứ tự làm: **SAU KHI** Phần 1, 2, 3.1, 3.2 (file này) xong.

---

## Phần 4 — Chi phí (cost dashboard, build THẬT)

Quyết định 2026-07-01: build thật. Cần agent-service instrument token usage của **2 lệnh gọi
LLM online** (`build_query`, `synthesize` — `honest_answer`/`direct_response` KHÔNG gọi LLM,
bỏ qua) ghi vào bảng mới, backend đọc trực tiếp bảng đó (cùng Postgres dùng chung, giống
pattern Phần 2 — backend query thẳng bảng do agent-service sở hữu, không cần HTTP proxy).

**Phạm vi cố ý loại trừ (nói rõ để khỏi nửa vời)**:
- **Embedding KHÔNG tính vào chi phí LLM.** `embed_texts` chạy model
  `AITeamVN/Vietnamese_Embedding` cục bộ (self-hosted, không qua API tính phí theo token như
  OpenAI) — không có "chi phí/token" kiểu billed-API để log. Chỉ track 2 lệnh gọi OpenAI
  (`build_query`, `synthesize`).
- **Không track chi phí indexing** (`run_graph_index.py`, `run_timeline_index.py` — các
  script offline gọi LLM trích entity/timeline). Dashboard này CHỈ cho luồng `/ask` online
  (per-câu-hỏi, "sinh động" theo hoạt động thật của user). Chi phí indexing là việc khác,
  không tự động lặp lại nên ít cần dashboard theo dõi liên tục.
- **Ước tính $ là client-side, KHÔNG lưu backend**: không có bảng giá LLM chính thức đủ tin
  cậy để hardcode cứng vào DB (giá thay đổi theo nhà cung cấp/model). Frontend cho admin tự
  nhập "giá ước tính $/1K token", nhân ngay trên UI — không phải giá thật, không persist.

### 4.1 agent-service — ghi token usage mỗi lệnh gọi LLM online

**Bảng `llm_usage`** (agent-service sở hữu DDL, giống `rag_chunks`/`timeline_events` — mới,
file `app/core/usage_log.py`):
```sql
CREATE TABLE IF NOT EXISTS llm_usage (
    id                UUID PRIMARY KEY,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    task              TEXT NOT NULL,  -- 'build_query' | 'synthesize'
    model             TEXT NOT NULL,
    prompt_tokens     INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens      INTEGER NOT NULL DEFAULT 0,
    user_id           TEXT  -- id user backend (TEXT, không FK — 2 service khác DB owner)
);
CREATE INDEX IF NOT EXISTS llm_usage_created_at_idx ON llm_usage (created_at);
CREATE INDEX IF NOT EXISTS llm_usage_user_id_idx ON llm_usage (user_id);
```
`id` sinh `uuid4()` ở app layer (khớp convention cả repo — không dùng `gen_random_uuid()` để
khỏi cần extension pgcrypto, xem `db.py` comment).

- **`app/core/usage_log.py::record_usage(task, model, prompt_tokens, completion_tokens,
  total_tokens, *, user_id=None, database_url=None) -> None`**: `psycopg.connect` trực tiếp
  (pattern `_database_url()` như `chunk_store.py`), INSERT 1 dòng, tự tạo bảng nếu chưa có
  (`ensure_llm_usage_table`, gọi 1 lần đầu mỗi call — idempotent `CREATE TABLE IF NOT
  EXISTS`). **Nuốt mọi exception** (try/except bọc toàn hàm, không raise) — ghi log usage lỗi
  KHÔNG ĐƯỢC làm fail câu trả lời thật, cùng triết lý với `build_visualization` (viz lỗi
  không fail answer).
- **agent-service — `app/schemas/ask.py::AskRequest`**: thêm field
  `user_id: str | None = None` (backend truyền id user đã xác thực xuống, để gắn usage vào
  đúng user cho breakdown "theo user"). KHÔNG phải field frontend gửi trực tiếp — backend tự
  điền từ JWT đã decode.
- **agent-service — `app/orchestrator/state.py::AgentState`**: thêm field
  `user_id: str | None`.
- **agent-service — `app/orchestrator/runner.py::initial_state`**: set
  `"user_id": request.user_id`.
- **agent-service — `app/orchestrator/synthesis.py::stream_synthesis`**: thêm kwarg
  `on_usage: Callable[[int, int, int], Awaitable[None]] | None = None` (prompt/completion/
  total tokens) — gọi (await) đúng 1 lần sau khi có usage từ response, mặc định `None` =
  không đổi hành vi hiện có (test cũ không truyền, không vỡ). **Cần thêm
  `stream_options={"include_usage": True}` vào lệnh gọi `client.chat.completions.stream(...)`
  để response có usage — VERIFY qua docs OpenAI Python SDK lúc code (CLAUDE.md "tra docs
  trước") vì streaming API mặc định KHÔNG trả usage nếu không bật cờ này; không giả định.**
- **agent-service — `app/orchestrator/nodes.py`**:
  - `build_query()`: sau khi có `completion` thành công, `usage =
    getattr(completion, "usage", None)`; nếu có, `await asyncio.to_thread(record_usage,
    task="build_query", model=_orchestrator_model(), prompt_tokens=usage.prompt_tokens,
    completion_tokens=usage.completion_tokens, total_tokens=usage.total_tokens,
    user_id=state.get("user_id"))` — bọc try/except riêng (không để lỗi log usage lọt vào
    nhánh except hiện có của build_query, vốn đang xử lý lỗi LLM chính).
  - `synthesize()`: truyền `on_usage=` một closure gọi `record_usage(task="synthesize",
    model=_orchestrator_model(), ..., user_id=state.get("user_id"))` (qua
    `asyncio.to_thread` bên trong closure vì `on_usage` là async).

### 4.2 backend — đọc trực tiếp + tổng hợp

Giống Phần 2 (`rag_chunks`/`timeline_events`): `llm_usage` do agent-service sở hữu DDL nhưng
backend **query thẳng** (cùng Postgres, không cần HTTP proxy) vì đây là dữ liệu dạng bảng đơn
giản (không phải Neo4j — chỉ Neo4j mới cần proxy qua agent_client).

> **Bảng `llm_usage` có thể CHƯA TỒN TẠI khi backend query** (khác `rag_chunks`/
> `timeline_events` — 2 bảng đó được tạo bởi **script indexing chạy 1 lần, luôn xong trước
> khi app chạy**; `llm_usage` lại tạo **lazy** ngay trong `record_usage()` — chỉ có bảng SAU
> lệnh gọi LLM đầu tiên, xem §4.1). Admin mở tab Chi phí trước khi có bất kỳ câu hỏi nào được
> hỏi qua flow mới → bảng chưa có → `psycopg.errors.UndefinedTable`. `core/errors.py` KHÔNG
> có handler chung cho `Exception` (chỉ `AppError`/`StarletteHTTPException`/
> `RequestValidationError`) → lỗi này sẽ lọt thành **500 thô**, không phải empty-state.
> **Bắt buộc** `list_usage_rows`/`list_top_users` tự bắt `psycopg.errors.UndefinedTable` →
> trả `[]` (coi bảng chưa tồn tại là "chưa có usage nào", cùng cách xử lý với
> `get_runtime_config()` ở `system-config-plan.md` cho `system_config` — nhất quán trong cả
> repo). `compute_cost_overview([])`/`compute_cost_by_day([])`/`compute_cost_by_task([])` vốn
> ĐÃ PHẢI xử lý input rỗng cho case "thật sự chưa có usage" nên không cần thêm code gì ở tầng
> pure-function — chỉ cần `list_usage_rows`/`list_top_users` không throw ra ngoài.

- **backend — `app/models/cost.py`** (mới, mirror `models/logs.py`):
  - `list_usage_rows(from_date?, to_date?) -> list[dict]` — SELECT thô toàn bộ cột từ
    `llm_usage` trong khoảng thời gian, KHÔNG tính toán trong SQL. Bắt
    `psycopg.errors.UndefinedTable` → trả `[]` (xem lưu ý trên).
  - `list_top_users(from_date?, to_date?, limit) -> list[dict]` — `SELECT u.id, u.email,
    u.name, sum(l.total_tokens) AS total_tokens, count(*) AS call_count FROM llm_usage l JOIN
    users u ON u.id::text = l.user_id WHERE ... GROUP BY u.id ORDER BY total_tokens DESC LIMIT
    %s` (JOIN được vì backend có driver cả 2 bảng trong cùng Postgres). Cùng bắt
    `psycopg.errors.UndefinedTable` → trả `[]`.
- **backend — `app/services/cost_service.py`** (mới, hàm THUẦN — cùng idiom
  `quality_service.py`): `compute_cost_overview(rows) -> CostOverview` (total_calls,
  total_tokens, total_prompt_tokens, total_completion_tokens, avg_tokens_per_call);
  `compute_cost_by_day(rows) -> list[DailyCost]` (group theo `created_at::date`, sort tăng
  dần — cho biểu đồ theo ngày); `compute_cost_by_task(rows) -> list[TaskCost]` (group theo
  `task`). Test thuần bằng dict giả, không cần DB — 3 hàm tách riêng cho dễ test từng phần.
- **backend — `app/schemas/cost.py`** + **`app/api/cost.py`** (prefix `/api/admin/cost`,
  `require_admin`):
  - `GET /api/admin/cost/overview?from_date&to_date` → `CostOverviewOut`.
  - `GET /api/admin/cost/by-day?from_date&to_date` → `DailyCostOut[]`.
  - `GET /api/admin/cost/by-task?from_date&to_date` → `TaskCostOut[]`.
  - `GET /api/admin/cost/top-users?from_date&to_date&limit=10` → `TopUserCostOut[]`
    (`user_id, email, name, total_tokens, call_count`).
- Đăng ký router trong `main.py`.

### 4.3 backend — gắn `user_id` vào request sang agent

- **`app/api/chat.py::ask`**: đã có dependency `user: User = Depends(get_current_user)` từ
  Phần 3.2 (quota) — tái dùng luôn, KHÔNG thêm dependency mới. Truyền
  `AgentAskRequest(question=..., history=..., stream=True, debug=..., user_id=user.id)`.
- **`app/services/agent_client.py::AgentAskRequest`**: thêm field `user_id: str | None =
  None`.

### 4.4 Test
> **`tests/conftest.py::_DB_MODULES` phải thêm `"app.models.cost"`** (xem lưu ý chung ở đầu
> file) — test insert `llm_usage`/`users` fixture qua `db_conn` rồi `list_usage_rows`/
> `list_top_users` đọc lại, nếu không patch `app.models.cost` sẽ đọc bằng connection thật.

- agent-service: `record_usage` insert đúng cột (test với DB giả/mock connect, hoặc chỉ test
  DDL statement hợp lệ); `build_query()` gọi `record_usage` đúng tham số khi completion có
  `usage`, **bỏ qua êm** khi mock completion KHÔNG có attribute `usage` (test hiện có dùng
  `SimpleNamespace` không có `.usage` → `getattr(..., "usage", None)` trả `None` → không gọi
  `record_usage`, không raise — test cũ KHÔNG cần sửa); `stream_synthesis` gọi `on_usage` với
  đúng 3 số khi fake completion có `usage`, KHÔNG gọi khi `on_usage=None` (mặc định, test cũ
  giữ nguyên).
- backend: `compute_cost_overview`/`compute_cost_by_day`/`compute_cost_by_task` test thuần
  bằng list dict giả (nhiều task/nhiều ngày/nhiều user) — không cần DB; endpoint
  `/api/admin/cost/*` trả đúng shape + `require_admin` chặn teacher; `list_top_users` JOIN
  đúng email; **regression quan trọng**: `list_usage_rows`/`list_top_users` khi bảng
  `llm_usage` CHƯA tồn tại (drop bảng hoặc test DB sạch chưa init) → trả `[]`, KHÔNG raise —
  và endpoint `/api/admin/cost/overview` (etc.) tương ứng trả `200` với số liệu rỗng (`0` lượt
  gọi, mảng rỗng), KHÔNG phải `500`.

**Lưu ý ripple qua test có sẵn**: KHÔNG cần sửa test hiện có của `build_query`/
`stream_synthesis` (cả hai đổi đều có default an toàn: `on_usage=None`, `getattr(...,
"usage", None)` — mock cũ không có usage vẫn chạy y hệt trước). Chỉ cần THÊM test mới, không
sửa test cũ — rủi ro thấp hơn hẳn so với `system-config-plan.md`.

---

## Thứ tự triển khai (backend/agent-service)

1. **Debug streaming** (Phần 1.1 + 1.2) — bắt buộc, làm cùng đợt frontend DebugPanel; test kèm.
2. **Read endpoints Module 5** (Phần 2): backend chunks/events (psycopg) → agent graph read
   → backend proxy entities → điều hướng chéo `chunk_id`; test từng lớp.
3. **Module 4 — 3 nhóm build thật trong file này** (Phần 3 + 4), theo thứ tự rủi ro tăng dần:
   1. Hội thoại & chất lượng (3.1) — read-only, không migration, an toàn nhất, làm trước.
   2. Người dùng & quota (3.2) — sửa thẳng schema `users` (drop + tạo lại, KHÔNG migration —
      dev chưa có user thật) + đụng `deps.py::get_current_user` (áp dụng cho MỌI request) —
      cẩn thận test không phá luồng auth hiện có.
   3. Chi phí (Phần 4) — bảng mới `llm_usage` + thêm 1 lệnh ghi (fire-and-forget, có
      try/except riêng, default an toàn `None`) vào `build_query()`/`stream_synthesis()`
      đang chạy ổn định. Rủi ro thấp hơn 3.2 (không đụng auth) nhưng vẫn chạm 2 file
      orchestrator — làm sau 3.1/3.2, trước khi đụng tới `system-config-plan.md`. **Verify
      `stream_options={"include_usage": True}` qua docs OpenAI SDK trước khi code** (§4.1).
4. **(Tùy chọn)** Persist debug (Phần 1.3) — nếu muốn xem lại lượt cũ, không bắt buộc.
5. **Cấu hình hệ thống** — plan riêng `docs/plan/system-config-plan.md`, làm SAU KHI 1–4 ở
   trên xong (nặng/rủi ro nhất, đụng cả orchestrator đang chạy ổn định).

> Phần 1–4 nằm ngoài `apps/frontend` nhưng bắt buộc để feature debug + inspector + admin
> nâng cao chạy thật; thực hiện trong cùng đợt triển khai frontend tương ứng, có test kèm.
