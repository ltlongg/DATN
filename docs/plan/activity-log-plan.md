# Activity Log — Plan chi tiết

> Log **theo dõi hoạt động hệ thống** ở mức API gateway: mỗi request tới `/api/*` ghi
> đúng **một dòng** — user bấm vào phần nào, phần đó **trả OK hay lỗi**, mất bao lâu,
> lỗi gì. Mục đích: admin nhìn phát biết "phần đó có đang chạy không", tóm được các sự
> cố (500 do bug SQL, agent-service chết...) mà không phải đọc log server thô.
>
> **Đây KHÔNG phải** trace RAG chi tiết (đã có conversation log + `llm_usage`), cũng
> không phải Langfuse/LangSmith (đã quyết không dùng — xem lý do cuối file).

## 1. Phạm vi & nguyên tắc

**Làm (in-scope):**
- 1 bảng `activity_log` (backend-owned) + middleware ghi tự động ở [main.py](../../apps/backend/app/main.py).
- 1 nhóm endpoint admin read-only để hiển thị feed + lọc.
- Ghi **mọi** request `/api/*` (cả OK lẫn error) → trả lời được cả "phần này có ai
  dùng không / tỉ lệ OK" lẫn "sự cố gần nhất".

**KHÔNG làm (non-goals — cố ý cắt cho gọn):**
- ❌ **Không** phân tier `slow` — chưa có ngưỡng đáng tin cho từng endpoint (đặc biệt
  `/ask` bình thường đã ~4s). `latency_ms` vẫn **ghi lại** để sau này đủ số liệu thật
  thì mới quyết ngưỡng; hiện tại KHÔNG dùng nó để phân loại.
- ❌ **Không** log request/response body — chỉ metadata.
- ❌ **Không** log stack trace / secret — cột `error` chỉ giữ *loại exception + message
  ngắn (≤200 ký tự)*.
- ❌ **Không** đụng agent-service — chất lượng/nội dung câu trả lời đã nằm ở conversation
  log; activity log chỉ quan tâm "request tới backend thành/bại".
- ❌ **Không** retention/cleanup tự động ở bản đầu (xem §7 Open questions).

## 2. Quyết định thiết kế (đã chốt)

| Quyết định | Chốt |
|---|---|
| Đặt ở đâu | **Backend middleware** (không phải `runner.py`) — để phủ mọi tính năng admin/chat, không chỉ `/ask`. |
| Severity | Chuỗi `'ok'` / `'error'`, suy từ `status_code >= 400`. **Không** boolean, **không** tier slow. |
| Ghi gì | Ghi **hết** request `/api/*` (OK + error). Feed sự cố = view lọc `severity='error'`. |
| Cột `error` | **GIỮ** (nullable) — thấy 500 mà không biết `AmbiguousColumn` thì vẫn phải đi mò. |
| request_id | Tái dùng `request.state.request_id` từ `RequestIDMiddleware` sẵn có. |
| Cách ghi | **Await** insert qua `anyio.to_thread` + **nuốt mọi exception** (log lỗi không được làm fail request). Await (không fire-and-forget) để deterministic khi test. |
| Sở hữu bảng | **Backend** — DDL vào `SCHEMA_STATEMENTS` ([db.py](../../apps/backend/app/core/db.py)). |

## 3. Schema

Thêm vào `SCHEMA_STATEMENTS` trong [db.py](../../apps/backend/app/core/db.py) (idempotent,
`CREATE TABLE IF NOT EXISTS`, UUID sinh ở app layer như các bảng khác):

```sql
CREATE TABLE IF NOT EXISTS activity_log (
    id          UUID PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    request_id  TEXT,
    user_id     TEXT,               -- best-effort từ JWT; NULL nếu request chưa auth
    method      TEXT NOT NULL,      -- GET / POST / ...
    path        TEXT NOT NULL,      -- /api/admin/kb/chunks/512, /api/chat/ask, ...
    status_code INTEGER NOT NULL,   -- 200 / 403 / 500 / 503 ...
    severity    TEXT NOT NULL,      -- 'ok' | 'error'  (status_code >= 400 -> 'error')
    latency_ms  INTEGER,
    error       TEXT                -- 'ProgrammingError: AmbiguousColumn ...' | NULL khi ok
);
CREATE INDEX IF NOT EXISTS idx_activity_log_created_at ON activity_log (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_activity_log_severity   ON activity_log (severity);
```

> ⚠️ **KHÔNG** tạo btree index trên `path`: filter path dùng `ILIKE '%...%'` (wildcard đầu
> chuỗi) → btree vô dụng cho kiểu match này. Data đồ án nhỏ, seq-scan chấp nhận được. Nếu sau
> này bảng lớn + cần lọc path nhanh → dùng **GIN + `pg_trgm`** (`CREATE INDEX ... USING gin
> (path gin_trgm_ops)`) hoặc đổi sang prefix search `LIKE 'path%'`. Xem §7.

Dùng `clock_timestamp()` (đồng bộ lý do với bảng `messages`): nhiều dòng ghi gần nhau vẫn
giữ thứ tự đúng.

**Ví dụ dữ liệu:**
```
| created_at          | user | method | path                     | status | severity | ms   | error                     |
|---------------------|------|--------|--------------------------|--------|----------|------|---------------------------|
| 2026-07-05 09:12:03 | u_02 | POST   | /api/chat/ask            | 200    | ok       | 4210 | NULL                      |
| 2026-07-05 09:12:40 | u_02 | GET    | /api/admin/kb/entities   | 200    | ok       | 180  | NULL                      |
| 2026-07-05 09:13:22 | u_07 | GET    | /api/admin/kb/chunks/512 | 500    | error    | 210  | ProgrammingError: ...     |
| 2026-07-05 09:14:01 | u_07 | POST   | /api/chat/ask            | 503    | error    | 5020 | agent-service unavailable |
```

## 4. Backend — các thành phần

### 4.1. DDL — `app/core/db.py`
Thêm khối `CREATE TABLE activity_log` + 3 index vào `SCHEMA_STATEMENTS`. Không cần đụng
`init_db.py` (nó gọi `init_schema` chạy toàn bộ tuple). Test fixture cũng tự có bảng.

### 4.2. Model — `app/models/activity.py` (mới)
Psycopg trực tiếp, mọi hàm SYNC (API gọi qua `anyio.to_thread`), mirror
[models/cost.py](../../apps/backend/app/models/cost.py):

- `record_activity(*, request_id, user_id, method, path, status_code, severity, latency_ms, error) -> None`
  - 1 câu `INSERT` (UUID `uuid4()` ở app layer).
  - **Nuốt mọi exception** (log `logger.warning`) — y hệt triết lý `record_usage`: ghi
    log hỏng KHÔNG được làm fail request thật.
- `list_activity(*, severity, path, from_date, to_date, limit, offset) -> tuple[list[dict], int]`
  - Trả rows + `total` (cho phân trang), `ORDER BY created_at DESC`.
  - Lọc tùy chọn: `severity` (`ok`/`error`), `path` (khớp `ILIKE %...%` để "lọc theo
    path"), khoảng ngày (tái dùng helper `_date_filters`).
  - Bảng backend-owned nên **luôn tồn tại** sau `init_db` → KHÔNG cần bắt `UndefinedTable`
    như `cost.py` (nhưng vẫn cứ để phòng vệ nếu muốn đồng nhất — tùy chọn).

### 4.3. Error handlers — `app/core/errors.py` (SỬA file có sẵn)
**Bắt buộc**, nếu không cột `error` mất thông tin cho lỗi *đã được handler bắt*. Hiện cả 3
handler ([errors.py:45-69](../../apps/backend/app/core/errors.py)) chỉ `return JSONResponse`,
không để lại `code` ở đâu cho middleware đọc. Lý do: `AppError`/`HTTPException` bị
`ExceptionMiddleware` (nằm TRONG `ActivityLogMiddleware`) biến thành response *trước khi* quay
ra tới middleware → middleware chỉ thấy `status_code`, KHÔNG thấy exception. Nếu không sửa,
mọi lỗi handled (`agent_bad_response` 502, `dependency_unavailable` 503, `validation_error`
422, `forbidden` 403...) chỉ log trơ `HTTP 503` — mất đúng thông tin activity log cần.

Sửa: mỗi handler set `code`/`message` lên `request.state` trước khi return. Vì `request` là
cùng object, middleware đọc lại được sau `call_next`:
```python
async def _app_error(request: Request, exc: AppError) -> JSONResponse:
    request.state.error_code = exc.code            # <-- thêm
    return JSONResponse(status_code=exc.status_code, content=_body(exc.code, exc.message))
# tương tự cho _http_error (dùng `code` đã tính) và _validation_error ("validation_error").
```
(Chữ ký handler đổi `_: Request` → `request: Request` để truy cập `.state`.)

### 4.4. Middleware — `app/main.py`
Thêm `ActivityLogMiddleware(BaseHTTPMiddleware)` (cùng file, cạnh `RequestIDMiddleware`):

```
async def dispatch(request, call_next):
    if không-nên-log(request):          # xem "bộ lọc" dưới
        return await call_next(request)
    start = time.perf_counter()
    error_text = None
    try:
        response = await call_next(request)
        status = response.status_code
    except Exception as exc:            # exception CHƯA được handler bắt (vd 500 thô)
        status = 500
        error_text = f"{type(exc).__name__}: {str(exc)[:200]}"
        # ghi log rồi RE-RAISE để error handler/Starlette xử lý như cũ
        await _safe_record(request, status, start, error_text)
        raise
    if status >= 400 and error_text is None:
        error_text = getattr(request.state, "error_code", None) or f"HTTP {status}"
    await _safe_record(request, status, start, error_text)
    return response
```

- **latency_ms** = `round((perf_counter()-start)*1000)`. Với SSE `/ask` (StreamingResponse)
  đây là thời gian tới *lúc mở stream* — đúng ý (lỗi *sau* khi mở đã có ở conversation log).
- **severity** = `'error' if status >= 400 else 'ok'`.
- **error (2 đường):** (a) exception CHƯA handled (500 thô như `ProgrammingError`) → bắt ở
  `except`, `error = "{type}: {msg[:200]}"`. (b) lỗi ĐÃ handled (AppError/HTTPException →
  response 4xx/5xx) → đọc `request.state.error_code` do handler set (**cần §4.3**); nếu vẫn
  None (an toàn) → fallback `f"HTTP {status}"`.
- **user_id (best-effort):** đọc header `Authorization: Bearer`, `decode_access_token` bọc
  `try/except` → lấy `sub`; lỗi/không có → `None`. **Không** đụng `deps.py` (tránh coupling;
  request chưa auth vẫn log được với user NULL).
- **request_id:** `getattr(request.state, "request_id", None)` (do `RequestIDMiddleware`
  set). ⚠️ **Thứ tự middleware:** phải để `RequestIDMiddleware` chạy TRƯỚC (bọc ngoài
  `ActivityLogMiddleware`) thì `request.state.request_id` mới sẵn. Starlette chạy
  middleware **thêm sau = bọc ngoài = chạy trước**, nên trong `create_app()` gọi:
  ```
  app.add_middleware(ActivityLogMiddleware)   # thêm TRƯỚC -> nằm TRONG
  app.add_middleware(RequestIDMiddleware)      # thêm SAU  -> bọc NGOÀI, set request_id trước
  ```
  (CORS thêm cuối cùng, ngoài cùng — không ảnh hưởng.)
- `_safe_record` = await `anyio.to_thread.run_sync(record_activity, ...)`, và bản thân
  `record_activity` đã nuốt exception nên middleware không bao giờ vỡ vì log.

**Bộ lọc `không-nên-log`:** bỏ qua để tránh rác —
- Path không bắt đầu bằng `/api/` (bỏ `/health`, `/ready`, static).
- `request.method == "OPTIONS"` (CORS preflight).
- (tùy chọn) bỏ chính endpoint đọc activity `/api/admin/activity` để feed không tự soi mình.

### 4.5. Schema Pydantic — `app/schemas/activity.py` (mới)
```python
class ActivityLogItem(BaseModel):
    id: str
    created_at: datetime
    request_id: str | None
    user_id: str | None
    method: str
    path: str
    status_code: int
    severity: str
    latency_ms: int | None
    error: str | None

class ActivityLogResponse(BaseModel):
    items: list[ActivityLogItem]
    total: int
    limit: int
    offset: int
```
(Có thể thêm `user_email` bằng cách JOIN `users` trong model nếu muốn hiển thị email thay
vì id — tùy chọn, mirror `logs.py`.)

### 4.6. Router — `app/api/activity.py` (mới)
Mirror [api/cost.py](../../apps/backend/app/api/cost.py), `dependencies=[Depends(require_admin)]`:

- `GET /api/admin/activity` → `ActivityLogResponse`
  - Query params: `severity`, `path`, `from_date`, `to_date`, `limit` (default 50, ≤200),
    `offset`.
  - Gọi `list_activity` qua `anyio.to_thread`.

Mount trong `create_app()`:
```python
app.include_router(activity.router, prefix="/api/admin/activity", tags=["admin-activity"])
```

### 4.7. Tests — `apps/backend/tests/test_activity.py` (mới) + SỬA `conftest.py`
**Bắt buộc trước khi viết test:** thêm `"app.models.activity"` vào `_DB_MODULES`
([conftest.py:28-37](../../apps/backend/tests/conftest.py)). Fixture patch `connection` theo
TỪNG module; thiếu dòng này → `record_activity` xài **pool thật**, ghi **ngoài** transaction
rollback → rò rỉ ra Postgres remote + test SELECT không thấy dòng vừa ghi.

Vì middleware **await** ghi (không fire-and-forget) nên các dòng ghi trong 1 request nằm cùng
transaction test và assert được ngay:
1. Một request `/api/...` thành công → có đúng 1 dòng `activity_log`, `severity='ok'`,
   `error IS NULL`, `latency_ms` ≥ 0, `request_id` khớp header `X-Request-ID` trả về.
2. Lỗi **handled** (vd gọi endpoint ném `AppError` 503 / dùng `mock_agent.configure(exc=...)`
   cho `/ask`) → dòng `severity='error'`, `error` = `error_code` từ handler (nhờ §4.3).
3. Lỗi **unhandled 500 thô**: `TestClient(app)` mặc định `raise_server_exceptions=True` →
   500 thô **ném exception trong test**, KHÔNG trả response để assert. Muốn test đường này
   phải `TestClient(app, raise_server_exceptions=False)`. **Khuyến nghị**: ưu tiên test bằng
   lỗi handled (case 2) — thực tế hơn; case unhandled chỉ cần 1 test nhỏ với client riêng.
4. `/health` → **không** tạo dòng nào (bộ lọc path không `/api/`).
5. `GET /api/admin/activity` bằng non-admin → 403 (`require_admin`); admin → 200, lọc
   `severity=error` chỉ trả dòng lỗi.
6. `user_id` gắn đúng khi request có Bearer hợp lệ; NULL khi không có token.

> ⚠️ Cốt lõi test isolation: `record_activity` phải ghi qua `connection()` (đã bị fixture
> patch thành `fake_connection` yield đúng connection test) — KHÔNG mở connection riêng. Cộng
> với việc có mặt trong `_DB_MODULES` ở trên, dòng ghi mới nằm trong transaction test và
> rollback dọn sạch. Đây cũng là lý do **await** (không task nền chạy sau khi test đã rollback).

## 5. Frontend — trang "Hoạt động hệ thống" (phase 2, sau khi backend xong)

> ⚠️ Nav admin **là route + sidebar dọc, KHÔNG còn tab ngang** (đã refactor xong). Mỗi chức
> năng admin = 1 route con + 1 `NavItem`. Làm theo đúng pattern hiện có, KHÔNG "đăng ký tab".

- `src/api/activity.ts` — mirror `api/cost.ts`: hàm `getActivity(params)` gọi
  `GET /api/admin/activity`, kèm type `ActivityLogItem` + `ActivityLogResponse`.
- `src/features/advanced/ActivityTab.tsx` — bảng "Luồng hoạt động / sự cố" mirror `CostTab`:
  - Cột: THỜI ĐIỂM · USER · METHOD · PATH · STATUS · THỜI LƯỢNG · LỖI · REQUEST ID.
  - Filter: dropdown severity (Tất cả / ok / error) + ô lọc theo path.
    (**Bỏ** filter request_id — backend §4.6 chưa có param này; request_id vẫn HIỂN THỊ ở cột,
    chỉ không lọc được. Thêm sau trivial: 1 WHERE ở model + 1 Query param.)
  - Badge severity: `error` đỏ, `ok` xanh nhạt.
  - Phân trang qua `limit`/`offset` (TanStack Query, `keepPreviousData`).
- `src/pages/AdminActivityPage.tsx` — wrapper mỏng bọc `ActivityTab` + `PageHeader` (mirror
  `AdminCostPage.tsx`).
- **Route:** thêm `{ path: "activity", element: <AdminActivityPage /> }` vào nhóm "Quản trị"
  trong [routes.tsx](../../apps/frontend/src/app/routes.tsx) (cạnh `logs`/`users`/`cost`). Cân
  nhắc lazy như `AdminCostPage` nếu trang nặng (bảng dài).
- **Sidebar:** thêm 1 `NavItem` vào `NAV_ITEMS` trong
  [AppSidebar.tsx](../../apps/frontend/src/components/AppSidebar.tsx): `{ to: "/admin/activity",
  label: "Hoạt động hệ thống", icon: <Activity/ hoặc icon lucide phù hợp>, end: false,
  adminOnly: true, group: "QUẢN TRỊ" }`.
- Test Vitest: render bảng từ mock response, filter severity đổi query param.

## 6. Thứ tự triển khai (phases)

1. **Schema** — thêm DDL vào `db.py` (`SCHEMA_STATEMENTS`); chạy `python scripts/init_db.py`
   (idempotent) tạo bảng.
2. **Model** — `models/activity.py` (`record_activity` nuốt exception + `list_activity`).
3. **Error handlers** — SỬA `core/errors.py`: 3 handler set `request.state.error_code` (§4.3).
4. **Middleware** — `ActivityLogMiddleware` + wiring đúng thứ tự trong `create_app()` (§4.4).
5. **API** — `schemas/activity.py` + `api/activity.py` + mount router.
6. **Tests backend** — SỬA `conftest.py` thêm `app.models.activity` vào `_DB_MODULES`; viết
   `test_activity.py` (chú ý `raise_server_exceptions` cho case 500 thô); chạy ruff + mypy +
   pytest.
7. **Frontend** — `api/activity.ts` + `ActivityTab.tsx` + `AdminActivityPage.tsx` + route
   (`routes.tsx`) + `NavItem` (`AppSidebar.tsx`) + test Vitest.
8. **Verify** — chạy backend, bắn vài request (1 OK, 1 lỗi handled cố ý), mở trang thấy dòng
   hiện ra + lọc severity hoạt động.

Backend (bước 1–6) độc lập với FE — có thể merge trước, FE làm sau. **File có sẵn phải sửa**:
`db.py`, `core/errors.py`, `main.py`, `tests/conftest.py`, `routes.tsx`, `AppSidebar.tsx`.

## 7. Open questions / để sau

- **Retention:** bảng ghi mọi request → lớn dần. Bản đầu KHÔNG cleanup. Sau này có thể
  thêm 1 job xóa `created_at < now() - interval '30 days'`, hoặc partition theo ngày. Với
  quy mô đồ án chưa cần.
- **Path có ID (high cardinality):** `/api/admin/kb/chunks/512`, `/api/sessions/<uuid>` làm
  path đa dạng — với **feed sự cố** thì không sao (hiển thị path thật user gọi). Nếu sau này
  muốn **thống kê gộp theo tính năng**, dùng route template Starlette
  (`request.scope["route"].path` → `/api/admin/kb/chunks/{chunk_id}`) lưu thêm cột
  `route_pattern`. Chưa làm ở bản đầu (giữ tối giản).
- **Ngưỡng slow:** sau khi có `latency_ms` thật một thời gian, phân tích p95 theo path rồi
  mới cân nhắc thêm tier `slow` (per-path threshold). Không đoán mò lúc này.

## 8. Vì sao KHÔNG dùng Langfuse/LangSmith (ghi lại quyết định)

Activity log này là **tính năng sản phẩm** cho admin (nằm trong UI của app, khán giả là
admin/giáo viên vận hành hệ thống). Langfuse/LangSmith là **công cụ observability cho dev**
(trace LLM, khán giả là lập trình viên) — khác đối tượng, không thay thế nhau. Đã quyết:
tự build log trong Postgres cho tính năng admin; LangSmith là SaaS trả phí + dữ liệu rời hệ
(loại); Langfuse (self-host, OSS) chỉ cân nhắc *sau này* như công cụ debug riêng cho dev nếu
còn thời gian, KHÔNG phải để thay bảng log này.
