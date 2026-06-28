# Backend API Gateway Plan

> Mục tiêu của plan này: dựng `apps/backend` thành API chính cho frontend, chịu trách
> nhiệm auth, role guard, conversation/session, proxy `/ask` sang agent-service, và admin
> document mock cho MVP. Backend KHÔNG tự làm RAG/LLM; phần đó thuộc `agent-service`.

## Bối cảnh

Repo hiện tại:

- `apps/backend/` gần như chưa build, mới có `requirements.txt`.
- `infra/compose/docker-compose.yml` đã định nghĩa backend là FastAPI gateway port `8000`.
- `.env.example` đã có:
  - `BACKEND_PORT=8000`
  - `BACKEND_SECRET_KEY`
  - `DATABASE_URL`
  - `AGENT_SERVICE_URL=http://localhost:9000`
- `docs/plan/orchestrator-plan.md` chốt: agent-service stateless, backend là source of
  truth cho conversation/history.
- `docs/design/frontend-scope.md` chốt 3 trang MVP:
  - đăng nhập
  - hỏi đáp
  - admin quản lý tài liệu

## Mục tiêu

Backend cần làm 5 việc chính:

1. Cung cấp API auth + role `admin` / `teacher`.
2. Lưu conversation và message history vào Postgres.
3. Nhận câu hỏi từ frontend, lấy bounded history, gọi internal `agent-service /ask`.
4. Proxy SSE streaming từ agent-service xuống frontend, đồng thời lưu kết quả cuối.
   **Backend chỉ chạy 1 chế độ STREAMING** — không expose non-stream ra frontend.
5. Cung cấp API admin quản lý tài liệu mock: list/create/delete/update trạng thái.

Backend không phải là agent. Backend chỉ điều phối user-facing API, persistence, auth,
và gateway tới agent-service.

## NOT In Scope

- Không tự gọi OpenAI.
- Không tự retrieve Qdrant/Neo4j.
- Không tự validate citation nội dung LLM.
- Không upload/xử lý PDF/DOCX/TXT thật trong MVP backend đầu tiên.
- Không build cost dashboard đầy đủ.
- Không build quota/rate limit nâng cao.
- Không build admin quality monitoring UI đầy đủ, chỉ chừa dữ liệu/log nền.

## Kiến trúc tổng

```text
Frontend
  |
  | REST/SSE + JWT
  v
Backend FastAPI
  |          \
  |           \ Postgres: users, conversations, messages, documents
  |
  | internal HTTP/SSE
  v
Agent-service /ask
  |
  v
Retrieval + LangGraph + synthesis + visualization
```

Backend giữ user/session/conversation. Agent-service nhận mỗi request độc lập:

```json
{
  "question": "...",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "stream": true,
  "debug": false
}
```

## Công nghệ đề xuất

- FastAPI cho HTTP API.
- Pydantic v2 cho request/response schema.
- `psycopg` trực tiếp cho Postgres — theo đúng pattern `chunk_store.py` của agent-service
  và convention CLAUDE.md (*"Postgres: dùng psycopg trực tiếp"*). **KHÔNG dùng ORM**
  (SQLAlchemy/SQLModel): backend chỉ có 4 bảng + CRUD đơn giản, ORM async nhiều bẫy và
  thêm một phong cách lạ vào repo. SQL tay minh bạch, dễ debug, dễ giải thích khi bảo vệ.
- Tạo bảng bằng **script `CREATE TABLE IF NOT EXISTS` chạy 1 lần** — **KHÔNG dùng Alembic**.
  Lý do: (1) agent-service vốn tạo bảng bằng script raw, không có migration → bỏ Alembic
  giữ cả repo nhất quán một kiểu; (2) Alembic autogenerate chỉ thấy 4 model backend, sẽ
  hiểu nhầm các bảng agent-service (`rag_chunks`, `timeline_events`, `gazetteer`) là thừa
  và **sinh lệnh DROP** — rủi ro mất dữ liệu đã tốn API index. Đổi cấu trúc về sau thì
  chạy `ALTER TABLE` tay (chấp nhận được ở quy mô đồ án).
- `httpx.AsyncClient` để gọi agent-service và proxy stream.
- JWT access token bằng `python-jose` hoặc `PyJWT`.
- Password hashing bằng `passlib[bcrypt]`.
- `pytest` + `httpx.AsyncClient` cho API tests (gom SSE stream rồi assert).

Giữ backend đơn giản. Không cần LangGraph, Celery, ORM, Alembic, hoặc service bus trong MVP.

## Cấu trúc thư mục dự kiến

```text
apps/backend/
  app/
    __init__.py
    main.py

    core/
      config.py
      security.py
      db.py
      errors.py

    models/
      user.py
      conversation.py
      document.py
      base.py

    schemas/
      auth.py
      chat.py
      document.py
      common.py

    api/
      __init__.py
      deps.py
      auth.py
      chat.py
      documents.py
      health.py

    services/
      agent_client.py
      conversation_service.py
      document_service.py

  scripts/
    init_db.py          # chạy 1 lần: CREATE TABLE IF NOT EXISTS cho 4 bảng backend
  tests/
    test_auth.py
    test_chat.py
    test_documents.py
    test_role_guard.py

  requirements.txt
  Dockerfile
  pytest.ini
```

## API Contract

### Health

```text
GET /health
GET /ready
```

`/health` chỉ báo process còn sống.

`/ready` kiểm tra:

- đọc được config bắt buộc
- kết nối được Postgres
- optional: ping `agent-service /ready`

### Auth

```text
POST /api/auth/login
GET  /api/auth/me
POST /api/auth/logout
```

`POST /api/auth/login`

```json
{
  "email": "teacher@example.com",
  "password": "password"
}
```

Response:

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "teacher@example.com",
    "name": "Teacher Demo",
    "role": "teacher"
  }
}
```

MVP có thể seed 2 user:

- `admin@example.com` / `admin123`
- `teacher@example.com` / `teacher123`

Chỉ dùng seed dev/demo, không hardcode password trong code production.

### Chat / Ask

```text
POST /api/chat/conversations
GET  /api/chat/conversations
GET  /api/chat/conversations/{conversation_id}
POST /api/chat/conversations/{conversation_id}/ask
```

`POST /api/chat/conversations`

```json
{
  "title": "Cuộc hỏi đáp mới"
}
```

Response:

```json
{
  "id": "uuid",
  "title": "Cuộc hỏi đáp mới",
  "created_at": "...",
  "updated_at": "..."
}
```

`POST /api/chat/conversations/{conversation_id}/ask`

Request (frontend KHÔNG chọn chế độ — backend luôn streaming):

```json
{
  "question": "Trương Định chống Pháp như thế nào?",
  "debug": false
}
```

Endpoint này luôn trả `text/event-stream` (SSE). Backend làm:

1. Kiểm tra user sở hữu conversation hoặc là admin.
2. Lưu user message.
3. Pre-generate `message_id` (UUID) cho assistant message sẽ lưu sau — để chèn được vào
   event `done` ngay cả khi nội dung còn đang stream.
4. Lấy tối đa `ask_max_history_messages` (= 12) message gần nhất làm bounded history.
5. Gọi `agent-service /ask` với `stream=true`.
6. Proxy SSE nguyên event xuống frontend, đồng thời gom event để tái dựng final response.
7. Khi stream kết thúc: lưu assistant message (dùng `message_id` đã pre-generate).

Lỗi trước khi stream mở (agent sập/không bắt máy) → trả HTTP 503/504 bình thường. Lỗi sau
khi stream đã mở → đi qua event `error` (xem Agent Client).

Streaming response giữ event type của agent-service:

```text
status
token
citations
visualization
clarification
regenerating
blocked
done
error
```

Backend không sửa nội dung token. Backend có thể thêm `conversation_id` / `message_id`
vào event `done` nếu frontend cần link message.

### Documents Admin MVP

```text
GET    /api/admin/documents
POST   /api/admin/documents
DELETE /api/admin/documents/{document_id}
PATCH  /api/admin/documents/{document_id}
```

Chỉ role `admin` được gọi.

MVP chỉ quản lý metadata mock, chưa upload file thật.

Document:

```json
{
  "id": "uuid",
  "name": "lichsu.clean.md",
  "type": "markdown",
  "status": "indexed",
  "chunk_count": 1213,
  "created_at": "...",
  "updated_at": "..."
}
```

`status`:

```text
draft | indexing | indexed | failed
```

## Database Schema

### users

```text
id              UUID PRIMARY KEY
email           TEXT UNIQUE NOT NULL
name            TEXT NOT NULL
role            TEXT NOT NULL  -- admin | teacher
password_hash   TEXT NOT NULL
is_active       BOOLEAN NOT NULL DEFAULT true
created_at      TIMESTAMPTZ NOT NULL
updated_at      TIMESTAMPTZ NOT NULL
```

### conversations

```text
id              UUID PRIMARY KEY
user_id         UUID NOT NULL REFERENCES users(id)
title           TEXT NOT NULL
created_at      TIMESTAMPTZ NOT NULL
updated_at      TIMESTAMPTZ NOT NULL
```

Index:

```text
idx_conversations_user_updated_at(user_id, updated_at DESC)
```

### messages

```text
id                    UUID PRIMARY KEY
conversation_id        UUID NOT NULL REFERENCES conversations(id)
role                  TEXT NOT NULL  -- user | assistant
content               TEXT NOT NULL
clarification_needed  BOOLEAN NOT NULL DEFAULT false
clarification_question TEXT
citations             JSONB NOT NULL DEFAULT '[]'
visualization         JSONB
retrieval_mode        TEXT NOT NULL DEFAULT 'none'
confidence            TEXT
warnings              JSONB NOT NULL DEFAULT '[]'
debug                 JSONB
created_at            TIMESTAMPTZ NOT NULL
```

Index:

```text
idx_messages_conversation_created_at(conversation_id, created_at)
```

### documents

```text
id              UUID PRIMARY KEY
name            TEXT NOT NULL
type            TEXT NOT NULL
status          TEXT NOT NULL
chunk_count     INTEGER NOT NULL DEFAULT 0
error_message   TEXT
created_by      UUID REFERENCES users(id)
created_at      TIMESTAMPTZ NOT NULL
updated_at      TIMESTAMPTZ NOT NULL
```

### answer_quality_events (chừa nền cho sau MVP)

MVP chưa cần UI đầy đủ, nhưng nên lưu bảng nhỏ để sau làm monitoring.

```text
id                UUID PRIMARY KEY
message_id         UUID REFERENCES messages(id)
user_id            UUID REFERENCES users(id)
rating             TEXT      -- up | down | neutral
reason             TEXT
created_at         TIMESTAMPTZ NOT NULL
```

API feedback có thể làm sau frontend chat:

```text
POST /api/chat/messages/{message_id}/feedback
```

## Auth & Role Guard

Role:

```text
teacher: dùng chat, xem conversation của chính mình
admin: dùng chat như teacher + truy cập /api/admin/*
```

Rule bắt buộc:

- Teacher không thấy admin route ở frontend.
- Teacher gọi thẳng `/api/admin/*` vẫn nhận `403`.
- User chỉ đọc/sửa conversation của chính mình.
- Admin có thể xem mọi conversation nếu sau này cần monitoring, nhưng MVP có thể chưa expose.

JWT payload:

```json
{
  "sub": "user_uuid",
  "role": "teacher",
  "exp": 1234567890
}
```

## Agent Client

`services/agent_client.py` chịu trách nhiệm duy nhất cho HTTP tới agent-service. Backend
chỉ gọi 1 chế độ: **streaming**.

Config timeout — với SSE, KHÔNG đặt giới hạn tổng thời gian (câu trả lời dài là bình
thường). Chỉ giới hạn lúc bắt kết nối, và "im lặng quá lâu giữa 2 token" (httpx `read`
reset mỗi lần có dữ liệu về, nên với stream nó chính là *idle timeout*):

```python
agent_service_url: str
agent_connect_timeout_seconds: int = 5    # chờ agent bắt máy
agent_read_idle_timeout_seconds: int = 30  # >30s không có token nào -> coi như treo, cắt

# httpx.Timeout(connect=agent_connect_timeout_seconds, read=agent_read_idle_timeout_seconds)
# KHÔNG bọc asyncio.wait_for(tổng) quanh stream -> tránh cắt ngang câu dài.
```

Stream (chỉ method này):

```python
async def ask_stream(request: AgentAskRequest) -> AsyncIterator[SseEvent]:
    ...
```

### Error mapping

**Điểm quan trọng cần nhớ:** vì backend chỉ gọi agent ở chế độ streaming, agent trả
`StreamingResponse` = **HTTP 200 ngay lập tức** (`app/api/ask.py`). Mọi lỗi retrieval/
synthesis xảy ra *sau đó* được agent **bắt lại và gửi thành event `error` trong dòng SSE**,
KHÔNG biến thành HTTP 503/504. Vì vậy backend hầu như chỉ gặp HTTP status lỗi ở **lúc mở
kết nối** (trước byte SSE đầu tiên); còn lỗi nghiệp vụ thì tới dưới dạng event.

Chia đúng theo 2 thời điểm:

**(a) Trước khi stream mở — còn đổi được HTTP status backend trả frontend:**

```text
không kết nối được agent (process chết / ref-used)  -> backend 503
httpx connect timeout (agent không bắt máy trong 5s) -> backend 504
agent trả 422 (backend gửi sai contract)             -> backend 502 + log mismatch
```

> Agent KHÔNG trả 503/504/500 cho lỗi nghiệp vụ ở chế độ stream — những status đó chỉ tồn
> tại trên đường non-stream nội bộ (test/eval), backend không bao giờ chạm tới. Đừng map chúng.

**(b) Sau khi stream đã mở — KHÔNG đổi được HTTP status nữa, mọi thứ đi qua event:**

```text
agent gửi event `error`   -> backend proxy nguyên event đó rồi đóng stream (không remap)
agent gửi event `blocked`  -> backend proxy nguyên event (guardrails chặn)
idle timeout (>30s không có token) -> httpx ReadTimeout -> backend tự emit event error:
```

```text
event: error
data: {"code":"backend_stream_failed","message":"Luồng trả lời bị gián đoạn."}
```

## Conversation Handling

Backend gửi history bounded cho agent-service.

Quy tắc:

- Lấy message theo `created_at ASC`.
- Chỉ gửi role `user` và `assistant`.
- Bỏ assistant message có `content` rỗng nếu đó chỉ là lỗi kỹ thuật.
- Nếu assistant trước đó là clarification question, vẫn đưa vào history để câu trả lời
  tiếp theo có ngữ cảnh.
- Cắt tối đa `ask_max_history_messages` (mặc định **12**) message gần nhất, đồng bộ với
  `AskRequest.history` của agent-service (đang `max_length=12` — gửi >12 sẽ bị 422).
- Cắt content quá dài nếu cần, nhưng tốt nhất reject question > 4000 chars từ frontend/backend.

Title conversation:

- Nếu user không nhập title, tạo title từ câu hỏi đầu tiên:
  - lấy 60-80 ký tự đầu
  - bỏ xuống dòng
  - không gọi LLM chỉ để đặt title

## SSE Persistence Strategy

Khi `stream=true`, backend vừa proxy event vừa gom dữ liệu để lưu message cuối.

Collector backend gom:

- `answer`: concat event `token.text`
- `citations`: event `citations.citations`
- `visualization`: event `visualization.visualization`
- `clarification_question`: event `clarification.question`
- `confidence`, `retrieval_mode`, `warnings`: event `done`
- nếu có `blocked` hoặc `error`: lưu assistant message trạng thái lỗi/ngắn gọn hoặc không lưu,
  tùy UX chốt sau

Trường hợp `regenerating`:

- clear buffer `answer`
- tiếp tục gom token lượt mới

Như vậy message lưu DB khớp nội dung frontend đã thấy.

## Frontend-Facing Types

Backend chỉ stream, nên không có "non-stream response". Toàn bộ nội dung tới frontend qua
các event SSE giữ nguyên type của agent-service; backend chỉ làm giàu thêm ở event `done`.

Stream final `done` (backend thêm `conversation_id` / `message_id` vào payload `done` gốc
của agent — vốn chỉ có `confidence`/`retrieval_mode`/`warnings`):

```json
{
  "conversation_id": "uuid",
  "message_id": "uuid",
  "confidence": "cao",
  "retrieval_mode": "hybrid",
  "warnings": []
}
```

Giá trị `confidence` có thể là một trong: `cao | vừa | thấp | không đủ dữ liệu | null`
(khớp `AnswerConfidence` của agent-service; clarification/smalltalk -> `null`).

## Error Handling

HTTP status:

```text
400 bad request
401 unauthenticated
403 forbidden
404 resource not found
409 conflict
422 validation error
503 dependency unavailable
504 timeout
500 unexpected backend bug
```

Error body:

```json
{
  "code": "agent_unavailable",
  "message": "Dịch vụ trả lời đang tạm thời không sẵn sàng."
}
```

Không trả stack trace hoặc secrets cho frontend.

## Observability

Log mỗi `/ask`:

- request id
- user id
- conversation id
- agent-service latency
- stream/non-stream
- route/retrieval_mode từ `done`
- confidence
- citation count
- warning count
- error code nếu có

MVP chưa cần distributed tracing, nhưng nên có `X-Request-ID` để debug.

## Test Plan

### Unit tests

- password hashing + verify.
- JWT create/decode/expired token.
- role guard teacher bị chặn `/api/admin/*`.
- conversation ownership guard.
- bounded history lấy đúng tối đa 12 message gần nhất.
- SSE collector xử lý `token`, `citations`, `visualization`, `done`.
- SSE collector xử lý `regenerating` bằng cách clear answer cũ.
- agent error mapping 503/504/network + connect/idle timeout (trước khi stream mở).

### API tests

- login thành công.
- login sai password -> 401.
- `/api/auth/me` trả user hiện tại.
- teacher tạo conversation.
- teacher hỏi (streaming), mock event stream của agent-service, backend proxy đúng event,
  lưu user + assistant message (gom token đúng nội dung frontend thấy).
- clarification path: backend lưu `clarification_needed=True`.
- admin list/create/delete document.
- teacher gọi admin document API -> 403.

### Integration smoke

- backend `/ready` ping Postgres.
- backend gọi agent-service `/ready`.
- end-to-end local:
  - login teacher
  - tạo conversation
  - ask (streaming), đọc hết event stream bằng curl
  - thấy message lưu lại đúng nội dung

## Implementation Order

1. Scaffold FastAPI backend:
   - `main.py`, config, health/ready, Dockerfile, requirements.
2. DB layer:
   - psycopg connection helper (`core/db.py`, theo mẫu `chunk_store.py`).
   - `scripts/init_db.py`: `CREATE TABLE IF NOT EXISTS` cho users/conversations/messages/documents.
3. Auth:
   - password hashing, JWT, current user dependency.
   - seed demo admin/teacher.
4. Role guard:
   - `require_admin`.
   - conversation ownership dependency.
5. Conversation APIs:
   - create/list/get conversation.
   - message persistence.
6. Agent client:
   - `ask_stream` (chỉ streaming), httpx timeout connect/idle.
   - error mapping sạch (trước khi stream mở).
7. Chat ask (streaming):
   - lấy history, pre-generate message_id, gọi agent-service `stream=true`.
   - proxy SSE + collector lưu final assistant message.
   - xử lý `regenerating`, `error`, `blocked`, client disconnect.
8. Admin documents mock:
   - list/create/update/delete.
9. Tests:
   - auth, role guard, conversation, agent client, SSE collector.
10. Local smoke:
   - chạy backend port 8000.
   - gọi qua frontend hoặc curl (đọc SSE).

## Acceptance Criteria

- Frontend có thể login và lấy `/api/auth/me`.
- Teacher không truy cập được `/api/admin/*`.
- Teacher tạo conversation và hỏi được qua backend.
- Backend gửi bounded history sang agent-service.
- Chat luôn streaming: proxy SSE đúng event order, gom token để lưu message cuối khớp nội
  dung frontend đã thấy.
- Clarification response được lưu và trả đúng cho frontend.
- Citation/visualization từ agent-service được giữ nguyên, không bị backend sửa sai.
- Admin quản lý document mock được.
- `/health` và `/ready` hoạt động.
- Tests cover auth, role guard, chat non-stream, chat stream, admin document.

## Sau MVP

- Upload tài liệu thật và queue indexing job.
- Conversation logs cho admin.
- Answer Quality Monitoring:
  - lọc câu trả lời confidence thấp
  - câu không có citation
  - câu bị user dislike
  - câu agent phải hỏi lại
- Cost dashboard:
  - token estimate
  - số request theo ngày/user
  - chi phí LLM/embedding nếu agent-service trả debug/cost metadata
- User/quota management.
- Rate limiting theo user/IP.
- Refresh token + revoke token.
- Audit log admin actions.
