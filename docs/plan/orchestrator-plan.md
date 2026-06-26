# Orchestrator And Ask API Plan

## Mục tiêu

Build agent-service online answer flow sau khi retrieval layer đã sẵn sàng:

- Nhận câu hỏi từ backend qua internal API `/ask`.
- Dùng LangGraph orchestrator để route, retrieve, kiểm tra đủ dữ liệu, synthesize answer.
- Trả câu trả lời tiếng Việt có citation đáng tin cậy.
- Gắn visualization payload từ timeline/map builder khi có dữ liệu.
- Không bịa khi corpus không đủ thông tin.

Plan này phụ thuộc vào `docs/plan/retrieval-layer-plan.md`.

## Trạng thái hiện tại

- `api/` chưa build.
- `orchestrator/` chưa build.
- Retrieval query-side cần build trước hoặc song song theo retrieval plan.
- Visualization builder đã có hướng online từ `retrieved_chunk_ids`, nhưng gazetteer/lat-lon đang tạm hoãn; timeline-only hoặc no-marker là trạng thái hợp lệ.
- Backend/frontend vẫn scaffold; agent-service `/ask` là internal endpoint để backend gọi sau.

## Quyết định chốt

### 1. Dùng LangGraph cho control flow

Bài toán có nhánh rõ ràng:

```text
request
  -> build query from question/history
  -> route
  -> retrieve
  -> sufficiency check
  -> synthesize or honest answer
  -> validate citations
  -> build visualization
  -> response
```

LangGraph phù hợp hơn tự viết state machine vì sau này có thể thêm retry/reflection/stream progress.

### 2. Default retrieval mode là hybrid

Router có thể phân loại intent, nhưng trong bản đầu:

- factual/history question -> `hybrid`
- relation/cause question -> vẫn `hybrid`, không graph-only
- greeting/meta/out-of-domain -> không retrieve hoặc honest answer tùy case
- ambiguous question -> có thể trả clarification thay vì cố retrieve

Graph-only và traditional-only chỉ nên là debug/eval/fallback.

### 3. Stateless multi-turn ở agent-service

Backend là source of truth cho conversation/session. Agent-service nhận `history` bounded từ backend:

- Không lưu memory dài hạn trong LangGraph bản đầu.
- Không dùng checkpointer cho conversation state.
- Dễ scale hơn, ít state ẩn hơn.

Sau này nếu cần streaming/resume sâu hơn thì thêm checkpointer sau.

### 4. Citation là trust boundary

LLM có thể trả `used_chunk_ids`, nhưng server không được tin mù.
Server phải validate:

- `used_chunk_ids` phải là subset của chunks đã retrieve.
- Drop id invalid.
- Dedupe và giữ order ổn định.
- Nếu answer có nội dung nhưng không có citation hợp lệ, chuyển sang honest answer hoặc retry synthesize một lần.

Structured output chỉ đảm bảo đúng shape, không đảm bảo factual/citation hợp lệ.

## NOT in scope

- Không build backend gateway.
- Không build frontend chat UI.
- Không làm auth/user/session persistence.
- Không re-index dữ liệu.
- Không chạy geocoding/gazetteer đang tạm hoãn.
- Không expose public API trực tiếp cho user.
- Không làm streaming token-by-token trong bản đầu.
- Không làm human-in-the-loop.

## API contract

### Route

```text
POST /ask
GET  /health
GET  /ready
```

`/ask` là internal endpoint cho backend gọi. Không coi agent-service là public API.

### Request schema

```python
from typing import Literal
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    debug: bool = False
```

Giới hạn history là bắt buộc để tránh prompt/context phình vô hạn.

### Response schema

```python
class Citation(BaseModel):
    chunk_id: str
    source_file: str | None = None
    chunk_index: int | None = None
    start_line: int | None = None
    end_line: int | None = None
    heading_path: list[str] = []
    quote: str | None = None


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    used_chunk_ids: list[str]
    retrieval_mode: str
    confidence: Literal["cao", "vừa", "thấp", "không đủ dữ liệu"]
    visualization: VisualizationPayload | None = None
    warnings: list[str] = []
    debug: dict[str, object] | None = None
```

`VisualizationPayload` reuse schema hiện có trong `app/schemas/visualization.py`.

## LangGraph state

```python
class AgentState(TypedDict):
    question: str
    history: list[ChatMessage]
    standalone_query: str
    route: RouteDecision | None
    retrieval: RetrievalResult | None
    sufficient: bool
    answer: str | None
    used_chunk_ids: list[str]
    citations: list[Citation]
    visualization: VisualizationPayload | None
    warnings: list[str]
    debug: dict[str, object]
```

## Graph flow

```text
START
  |
  v
build_query
  |
  v
route_intent
  |
  +------------------+
  |                  |
  v                  v
retrieve          honest_answer / clarification
  |
  v
check_sufficiency
  |
  +------------------+
  | sufficient       | insufficient
  v                  v
synthesize        honest_answer
  |
  v
validate_citations
  |
  v
build_visualization
  |
  v
END
```

## Nodes

### 1. `build_query`

Input:

- current question
- bounded history

Output:

- `standalone_query`

Rules:

- Nếu không có history: query = question.
- Nếu có history: dùng LLM hoặc deterministic prompt nhỏ để rewrite câu hỏi nối tiếp thành câu độc lập.
- Không thêm facts ngoài history.
- Nếu rewrite fail: fallback question gốc + warning.

MVP có thể bỏ rewrite LLM và chỉ truyền question gốc nếu muốn giảm scope, nhưng schema vẫn giữ `standalone_query`.

### 2. `route_intent`

Output:

```python
class RouteDecision(BaseModel):
    kind: Literal["history_question", "clarification_needed", "out_of_scope", "smalltalk"]
    retrieval_mode: Literal["hybrid", "traditional", "graph", "none"]
    reason: str
```

Rules:

- Default `history_question` -> `hybrid`.
- Relation/cause/comparison vẫn -> `hybrid`.
- `traditional`/`graph` chỉ dùng nếu request debug/eval sau này chỉ định.
- Out-of-scope hoặc smalltalk có thể skip retrieval.

### 3. `retrieve`

Gọi retrieval layer:

```python
result = await retrieve_hybrid(standalone_query)
```

Error behavior:

- Partial backend failure từ retrieval layer -> giữ result + warnings.
- All backend failure -> raise dependency error để API trả 503.
- Empty result -> không raise; để `check_sufficiency` xử lý.

### 4. `check_sufficiency`

MVP deterministic:

- `sufficient = len(retrieval.chunks) >= 1`
- Nếu retrieval layer có `final_score`/`rrf_score` quá thấp sau này thì thêm threshold.
- Nếu top chunks toàn warning/hub/debug low confidence thì `sufficient = False`.

Không nên phụ thuộc tuyệt đối vào một numeric threshold ngay từ đầu vì vector score, graph score,
RRF và rerank score không cùng thang đo.

### 5. `synthesize`

Dùng OpenAI async structured output.

Output LLM:

```python
class SynthesizedAnswer(BaseModel):
    answer: str
    used_chunk_ids: list[str]
    confidence: Literal["cao", "vừa", "thấp", "không đủ dữ liệu"]
    missing_information: str | None
```

Prompt rules:

- Chỉ trả lời dựa trên retrieved chunks.
- Nếu chunks không đủ, nói rõ chưa đủ thông tin.
- Không đưa fact không có trong context.
- Mỗi claim chính phải có ít nhất một `used_chunk_id`.
- Trả lời tiếng Việt, giọng rõ ràng cho giáo viên/học sinh.

### 6. `validate_citations`

Server-side mandatory:

```text
LLM used_chunk_ids
  -> filter id in retrieved_chunk_ids
  -> dedupe
  -> build Citation from metadata
  -> if empty while answer claims facts: honest fallback or retry once
```

Không cho citation tới chunk không nằm trong retrieval result.

Quote nếu có chỉ lấy đoạn ngắn từ chunk text, không bắt LLM tự bịa quote.

### 7. `honest_answer`

Dùng khi:

- route out-of-scope
- retrieval empty
- sufficiency false
- synthesize/citation validation fail

Ví dụ:

```text
Mình chưa tìm thấy đủ thông tin trong corpus hiện có để trả lời chắc chắn câu này.
Bạn có thể hỏi cụ thể hơn về nhân vật, mốc thời gian hoặc sự kiện không?
```

### 8. `build_visualization`

Input:

- Prefer `used_chunk_ids` đã validate.
- Nếu không có used ids nhưng retrieval đủ: có thể dùng top retrieved ids, nhưng nên warning.

Output:

- `VisualizationPayload | None`

Rules:

- Timeline-only là hợp lệ.
- No marker là hợp lệ vì gazetteer/lat-lon đang tạm hoãn.
- Không ép sinh marker nếu thiếu tọa độ.
- Visualization failure không làm fail answer; trả answer + warning.

## OpenAI client

Thêm async client trong `app/core/llm.py`:

```python
@lru_cache(maxsize=1)
def get_async_openai_client() -> AsyncOpenAI:
    ...
```

Dùng model config riêng:

```python
orchestrator_llm_model: str | None = None
```

Nếu `orchestrator_llm_model is None`, fallback `llm_model`.

## Config knobs

Thêm vào `Settings`:

```python
orchestrator_llm_model: str | None = None
ask_max_history_messages: int = 12
ask_max_question_chars: int = 4000
ask_timeout_seconds: int = 60
orchestrator_retry_synthesize_once: bool = True
```

Không thêm quá nhiều config trước khi có eval.

## Error handling API

```text
422 - request validation error
503 - dependency unavailable: Qdrant/Neo4j/Postgres/OpenAI
504 - timeout
500 - unexpected bug, clean error body
```

Response lỗi không dump stack trace hoặc secrets.

`/health`:

- process alive.

`/ready`:

- kiểm tra config cơ bản.
- optional lightweight ping Postgres/Qdrant/Neo4j/OpenAI nếu không quá chậm.

## Observability/debug

MVP log nên có:

- request id
- route decision
- retrieval mode
- số candidates từng backend
- số chunks sau fusion/rerank
- used_chunk_ids
- warnings
- latency từng node

Nếu `debug=false`, response không trả debug chi tiết.

## Test plan

### Test diagram

```text
/ask
  -> validate request
  -> build_query
  -> route
      ├─ history question -> retrieve
      ├─ out_of_scope -> honest answer
      └─ smalltalk -> direct answer or honest response
  -> retrieve
      ├─ chunks found
      ├─ empty
      ├─ partial backend warning
      └─ dependency fail
  -> synthesize
      ├─ valid used_chunk_ids
      ├─ invalid used_chunk_ids
      ├─ no citations
      └─ LLM timeout/error
  -> visualization
      ├─ timeline only
      ├─ map + timeline
      ├─ no events
      └─ builder error
```

### Unit tests

- route defaults history questions to hybrid.
- relation/cause questions still route hybrid.
- bounded history validation rejects too long history.
- retrieve empty -> honest answer, no hallucinated citation.
- retrieval dependency error -> API 503.
- synthesize invalid `used_chunk_ids` -> filtered/dropped.
- synthesize claims answer but no valid citations -> honest fallback or retry.
- citation metadata builds from chunk metadata.
- visualization builder receives validated `used_chunk_ids`.
- visualization builder error returns answer + warning.
- gazetteer empty/no markers still returns valid response.

### API tests

- `POST /ask` happy path with mocked retrieval + mocked LLM.
- `POST /ask` validation 422 for empty question.
- `POST /ask` history too large -> 422.
- `POST /ask` OpenAI timeout -> 504 or clean 503 depending exception mapping.
- `GET /health` returns alive.
- `GET /ready` returns dependency/config readiness.

### Prompt/eval cases

Add small eval fixtures for:

- “Trương Định chống Pháp như thế nào?”
- “Phan Bội Châu liên quan gì đến Cường Để?”
- “Nguyễn Ái Quốc có vai trò gì trong việc thành lập Đảng?”
- one out-of-corpus question.
- one ambiguous follow-up requiring history.

Expected:

- answer grounded in retrieved chunks,
- citations valid subset,
- no fabricated marker/location.

## Implementation order

1. Build retrieval layer plan first.
2. Add `schemas/ask.py` or equivalent API/orchestrator schemas.
3. Add async OpenAI client.
4. Add synthesize prompt + structured output schema.
5. Add orchestrator state + nodes.
6. Add FastAPI router `/ask`, `/health`, `/ready`.
7. Add citation validation.
8. Add visualization integration.
9. Add tests with mocked retrieval/LLM/visualization.
10. Run ruff/mypy/pytest.

## Acceptance criteria

- `/ask` trả answer tiếng Việt grounded bằng retrieved chunks.
- Citations luôn là subset của retrieved chunks.
- Empty/insufficient data trả honest answer, không bịa.
- Hybrid là default retrieval path.
- History bị giới hạn rõ ràng.
- Visualization không làm fail answer nếu thiếu marker/gazetteer.
- API lỗi dependency/timeout có status code sạch.
- Tests cover happy path, insufficient path, invalid citation path và dependency failure.

