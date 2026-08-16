# Orchestrator And Ask API Plan

> **Cập nhật 2026-06-27** (5 điểm, đọc trước khi code):
> (1) **Clarification flow** — thêm node `clarify` khi câu hỏi mơ hồ, trả về ngay
> `clarification_question` mà KHÔNG checkpointer (clarify xảy ra TRƯỚC retrieve, không có
> gì cần lưu giữa hai request); frontend nhận → hiển thị → user trả lời → request mới
> kèm history → graph chạy lại bình thường. Xóa dòng "Không làm HITL" khỏi NOT-in-scope.
> (2) **Gộp entity extraction vào `build_query`** — call LLM rewrite trả structured output
> `{standalone_query, mentioned_entities, route}`, zero latency thêm; `seed_mentions` là
> field mới trong `AgentState`, truyền xuống `retrieve_hybrid(..., seed_mentions=...)`.
> (3) **`has_context` (tên cũ `check_sufficiency`)** — chỉ check `len(chunks) > 0`.
> `SynthesizedAnswer.confidence` là metadata tự đánh giá của LLM; từ 2026-08-03,
> `"không đủ dữ liệu"` không tự thu hồi answer có citation hợp lệ. Model trả lời phần có
> căn cứ và tự kết bằng lời lưu ý phù hợp với thông tin còn thiếu.
> (4) **`graph_context` phải vào `synthesize`** — prompt render 2 khối riêng: chunk text
> (đường provenance) và graph_context (quan hệ đã chưng cất); đây là contribution chính
> của đồ án, không render thì công sức GraphRAG bị bỏ phí.
> (5) **Retry synthesize** — conditional edge `validate_citations` → `synthesize` tối đa
> 1 lần (tổng 2 lần synthesize), sau đó → `honest_answer`; field `synthesize_attempt_count`
> (tăng sau mỗi synthesize, retry nếu `< 2`) guard chống loop.
>
> **Cập nhật 2026-06-27 (review lần 2)**: (a) `retrieval_mode: Literal["hybrid","none"]
> = "none"`, chỉ set `"hybrid"` sau node `retrieve` (clarify/smalltalk không retrieve);
> (b) `RouteDecision = Literal[...]` định nghĩa MỘT chỗ, dùng lại ở `BuildQueryOutput` +
> `AgentState`; (c) `mentioned_entities` trích từ `standalone_query` đã rewrite (không
> phải `question` raw) để follow-up vẫn có seed; (d) response schema dùng
> `Field(default_factory=list)` theo convention codebase.
>
> **Cập nhật 2026-06-27 (giản lược + streaming)**: (a) bỏ `used_chunk_ids` khỏi
> `AskResponse` (derive từ citations), bỏ field `has_context` khỏi state (dùng conditional
> edge), bỏ `missing_information` khỏi `SynthesizedAnswer`; (b) **streaming SSE giờ
> IN-SCOPE** (xem §Streaming) — `answer` đặt field đầu để stream trước, citations validate
> ở cuối, hòa giải với citation-as-trust-boundary; lỗi sau khi SSE mở đi qua event `error`.
> (c) **Stream theo BATCH, không phải token thô** — gom token vào cụm/câu rồi qua
> guardrails hook mới emit, để plan guardrails (riêng) chặn được nội dung TRƯỚC khi tới
> user; plan này chỉ dựng cơ chế batch + hook, không hiện thực luật guardrails.

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
  -> build query from question/history (+ trích entity + route)
  -> route
  -> retrieve
  -> has_context
  -> synthesize or honest answer
  -> validate citations
  -> build visualization
  -> response
```

LangGraph phù hợp hơn tự viết state machine: có `.astream_events()` để stream cả tiến
trình node lẫn token LLM (xem Streaming — đã in-scope), và sau này dễ thêm retry/reflection.

### 2. Chỉ một chế độ retrieval duy nhất: hybrid

Production chỉ dùng `hybrid` — không expose traditional hay graph-only ra flow. Lý do:

- Hybrid đã bao gồm cả vector search lẫn graph expansion bên trong
- Tách mode làm phức tạp flow mà không đem lại giá trị cho user
- Traditional và graph vẫn tồn tại ở tầng retrieval nhưng chỉ dùng trong script eval/ablation để đo số liệu báo cáo

`retrieve` node gọi thẳng `retrieve_hybrid()`, không cần config hay switch mode.

### 3. Stateless multi-turn ở agent-service

Backend là source of truth cho conversation/session. Agent-service nhận `history` bounded từ backend:

- Không lưu memory dài hạn trong LangGraph bản đầu.
- **Không dùng checkpointer** — clarification flow (hỏi lại user khi câu mơ hồ) xảy ra
  TRƯỚC retrieve, tức graph chưa làm gì nặng khi phát hiện mơ hồ. Graph kết thúc hoàn
  toàn, trả về `clarification_question`. Request tiếp theo kèm history → graph chạy lại
  bình thường. Không có state dở dang cần lưu → checkpointer không đem lại giá trị.
- Lưu lịch sử chat vĩnh viễn là việc của **backend** (Postgres, `conversations` table),
  không phải agent-service.
- Dễ scale hơn, ít state ẩn hơn.

Thêm checkpointer sau nếu cần pause mid-graph (ví dụ clarify SAU retrieve), nhưng không
làm cho MVP.

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
- Không dùng LangGraph `interrupt()` / checkpointer (clarify trả về ngay, không pause graph).
- Không hiện thực luật guardrails (thuộc plan guardrails riêng) — plan này CHỈ dựng cơ chế
  stream theo batch + chừa hook để guardrails cắm vào sau.

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

# Single source of truth — dùng lại ở BuildQueryOutput.route và AgentState.route.
RouteDecision = Literal["needs_retrieval", "ambiguous", "out_of_scope", "smalltalk"]

class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)

class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    stream: bool = True       # True → SSE; False → gom hết event trả 1 JSON (test/backend đơn giản)
    debug: bool = False
```

Giới hạn history là bắt buộc để tránh prompt/context phình vô hạn. `stream=False` chạy
đúng cùng graph nhưng gom toàn bộ event lại rồi trả một `AskResponse` JSON — tiện cho test
và cho caller không cần streaming.

### Response schema

```python
class Citation(BaseModel):
    chunk_id: str
    source_file: str | None = None
    chunk_index: int | None = None
    start_line: int | None = None
    end_line: int | None = None
    heading_path: list[str] = Field(default_factory=list)
    quote: str | None = None

class AskResponse(BaseModel):
    # Nếu clarification_needed=True thì answer=None, các field còn lại rỗng.
    # Frontend nhận → hiển thị clarification_question → user trả lời → request mới.
    clarification_needed: bool = False
    clarification_question: str | None = None
    answer: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    # used_chunk_ids đã bỏ khỏi response — derive từ [c.chunk_id for c in citations].
    # "none" khi không retrieve (clarify/smalltalk/out_of_scope); chỉ set "hybrid" sau retrieve.
    retrieval_mode: Literal["hybrid", "none"] = "none"
    confidence: Literal["cao", "vừa", "thấp", "không đủ dữ liệu"] | None = None
    visualization: VisualizationPayload | None = None
    warnings: list[str] = Field(default_factory=list)
    debug: dict[str, object] | None = None
```

`VisualizationPayload` reuse schema hiện có trong `app/schemas/visualization.py`. Khi
`stream=True`, `AskResponse` không trả nguyên khối mà được **tái dựng từ chuỗi event** (xem
Streaming) — `AskResponse` là dạng "đã gom đủ" tương đương `stream=False`.

## Streaming (SSE)

`/ask` mặc định stream qua **Server-Sent Events** (`text/event-stream`). Backend proxy
nguyên luồng SSE xuống frontend. Dùng LangGraph `.astream_events()` để bắt cả tiến trình
node lẫn token LLM.

### Stream theo BATCH, không phải token thô (để guardrails chặn được)

> **Quan trọng**: KHÔNG emit thẳng từng token LLM ra user. Một khi token đã gửi qua SSE thì
> không rút lại được → guardrails (plan riêng) sẽ không có cơ hội chặn nội dung xấu. Vì vậy
> orchestrator **gom token vào batch** (cụm/câu hoàn chỉnh), mỗi batch đi qua **một hook
> kiểm tra** rồi mới emit. Đây là điểm để plan guardrails cắm vào sau — plan này chỉ dựng
> cơ chế batch + chừa hook, KHÔNG hiện thực luật guardrails.

Cơ chế:

- Buffer token delta của `answer` cho tới ranh giới batch: gặp dấu kết câu (`. ! ? \n`)
  HOẶC đủ `stream_batch_chars` ký tự — cái nào tới trước.
- Mỗi batch hoàn chỉnh → **guardrails hook** (no-op ở plan này; plan guardrails thay bằng
  check thật) → nếu pass thì emit event `token` chứa batch; nếu hook chặn → emit `blocked`
  + dừng stream (các batch SẠCH đã emit trước đó giữ nguyên, không retract).
- Guardrails chặn được vì check xảy ra TRONG buffer, TRƯỚC khi byte rời server.

Đánh đổi: độ trễ ở mức batch (câu) thay vì token — chấp nhận được để có chỗ chặn an toàn.

### Vấn đề phải xử lý: streaming ↔ citation validation

Citation validation chạy SAU synthesize. Nếu stream answer live rồi validation fail → đã
hiển thị câu sai, phải rút lại. Cách hòa giải:

- **Structured Outputs có streaming**: đặt `answer` là field ĐẦU trong `SynthesizedAnswer`
  → token `answer` stream ra trước, `used_chunk_ids` + `confidence` đến ở cuối.
- Buffer answer thành batch (như trên); khi `used_chunk_ids` về (cuối) → validate → emit
  event `citations`.
- Frontend render citation từ list ĐÃ validate, không parse text thô.
- Trường hợp hiếm (0 citation hợp lệ sau khi đã stream hết answer): emit `regenerating`,
  frontend clear phần answer, stream lại — chặn bởi `synthesize_max_attempts`.

Như vậy answer đi qua **2 cổng** trước khi user tin được: guardrails (mỗi batch, lúc stream)
và citation validation (cuối, toàn câu).

### Event types

```text
status        — tiến trình node: {"node": "retrieve", "msg": "đang tìm tài liệu"}
token         — MỘT BATCH answer đã qua guardrails hook: {"text": "..."}  (trong synthesize)
citations     — citation đã validate (cuối synthesize): {"citations": [...]}
visualization — payload viz (sau build_visualization): {"visualization": {...}}
clarification — câu hỏi làm rõ (nhánh ambiguous, terminal): {"question": "..."}
regenerating  — báo retry synthesize, frontend clear answer đã stream
blocked       — guardrails hook chặn một batch, stream dừng (chi tiết: plan guardrails)
done          — tóm tắt cuối: confidence, retrieval_mode, warnings
error         — lỗi: {"code": "...", "message": "..."}   (xem Error handling)
```

### Streaming ở các nhánh không retrieve

- `clarify` → emit `clarification` rồi `done`, không có `token`.
- `direct_response` / `honest_answer` → text ngắn, vẫn batch + stream qua `token` cho đồng nhất.

## LangGraph state

```python
class AgentState(TypedDict):
    question: str
    history: list[ChatMessage]
    standalone_query: str
    seed_mentions: list[str]          # entity mentions trích từ LLM trong build_query
    route: RouteDecision | None       # RouteDecision = Literal[...] định nghĩa ở schema block
    clarification_needed: bool        # True → graph kết thúc sớm, trả clarification
    clarification_question: str | None
    retrieval: RetrievalResult | None
    # has_context KHÔNG lưu thành field — là conditional edge đọc thẳng len(retrieval.chunks).
    answer: str | None
    synthesize_attempt_count: int     # tăng sau MỖI synthesize; retry nếu < synthesize_max_attempts
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
build_query      (rewrite + seed_mentions + route — 1 LLM call)
  |
  v
route_intent
  |
  +------------------+------------------+------------------+
  |                  |                  |                  |
  v                  v                  v                  v
retrieve         clarify          honest_answer     direct_response
(needs_retrieval)(ambiguous)      (out_of_scope)    (smalltalk)
  |                  |                  |                  |
  v                  v                  v                  v
has_context         END               END               END
  |           (clarification_
  +--------+   question trả về,
  |        |   request sau kèm
  v        v   history → bình thường)
synthesize honest_answer
  |        (chunks rỗng)
  v
validate_citations
  |
  +----------+
  | ok       | fail + attempt_count < max
  v          v
  |       synthesize (retry, tối đa 1 lần)
  |          |
  v          v
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

Output (1 LLM call, structured output):

```python
class BuildQueryOutput(BaseModel):
    standalone_query: str
    mentioned_entities: list[str]   # entity tường minh trong standalone_query
    route: RouteDecision            # Literal[...] định nghĩa ở schema block
```

Gộp rewrite + entity extraction + routing vào **1 call duy nhất** — zero latency thêm so
với chỉ rewrite. `mentioned_entities` ghi vào `AgentState.seed_mentions`, truyền xuống
`retrieve_hybrid(..., seed_mentions=...)` để graph retriever không phải tự token-match.

Rules:

- Nếu không có history: `standalone_query = question`.
- Nếu có history: rewrite câu nối tiếp thành câu độc lập đủ ngữ cảnh.
- `mentioned_entities`: liệt kê entity xuất hiện tường minh **trong `standalone_query`
  sau khi rewrite** (không phải câu `question` raw) — không suy diễn ngoài history/context.
  Nhờ vậy follow-up "Ông ấy làm gì sau đó?" → rewrite "Trương Định làm gì sau đó?" →
  `seed_mentions = ["Trương Định"]` (resolve từ history), thay vì rỗng. Câu thật sự mơ hồ
  không resolve được thì để rỗng + `route = "ambiguous"`, đừng ép LLM đoán.
- `route = "ambiguous"` khi câu dùng đại từ không rõ ("ông ấy", "sự kiện đó", "trận đánh
  đó") mà history không đủ để resolve.
- Nếu LLM call fail: fallback `standalone_query = question`, `mentioned_entities = []`,
  `route = "needs_retrieval"` + warning.

### 2. `route_intent`

Node này chỉ đọc `AgentState.route` (đã có từ `build_query`) và điều hướng — **không gọi
LLM thêm**. Routing logic đã nằm trong `build_query` output.

Điều hướng:

- `needs_retrieval` → `retrieve` (gọi thẳng `retrieve_hybrid`, không switch mode)
- `ambiguous` → `clarify`
- `out_of_scope` → `honest_answer`
- `smalltalk` → `direct_response`

Default nếu `route` chưa set: `needs_retrieval` → `retrieve`.

### 3. `retrieve`

Gọi retrieval layer, truyền `seed_mentions` từ state:

```python
result = await retrieve_hybrid(standalone_query, seed_mentions=state["seed_mentions"])
```

Node này set `retrieval_mode = "hybrid"` cho response. Các nhánh không đi qua đây
(clarify/smalltalk/out_of_scope) giữ default `"none"`.

Error behavior:

- Partial backend failure từ retrieval layer -> giữ result + warnings.
- All backend failure -> raise dependency error để API trả 503.
- Empty result -> không raise; để `has_context` xử lý.

### 4. `has_context`

**Đây là conditional edge, không phải node ghi state** — chỉ đọc `retrieval` để rẽ nhánh,
không lưu field nào. Chỉ kiểm tra có chunk nào không, không phán đoán "đủ để trả lời" (đó
là việc của LLM ở `synthesize`). Lý do không dùng ngưỡng phức tạp: hybrid + rule-B gần như
luôn trả ≥1 chunk kể cả câu ngoài domain, nên threshold số không lọc được honest-answer path.

```python
# conditional edge function
def has_context(state) -> str:
    return "synthesize" if state["retrieval"].chunks else "honest_answer"
```

- có chunk → `synthesize`.
- không chunk → thẳng `honest_answer` (skip synthesize).

Phán đoán "chunks này có thực sự trả lời được câu hỏi không?" giao cho LLM trong
`synthesize` — LLM có full context (câu hỏi + chunks) để tự đánh giá confidence. Confidence
không phải kiểm chứng độc lập: answer có citation hợp lệ vẫn được giữ; nếu thiếu thông tin,
model tự nói rõ phần giới hạn ở cuối answer.

### 5. `synthesize`

Dùng OpenAI async structured output **có streaming**.

Output LLM:

```python
class SynthesizedAnswer(BaseModel):
    answer: str                 # PHẢI là field đầu → token stream ra trước
    used_chunk_ids: list[str]   # LLM khai raw → validate_citations lọc thành citations
    confidence: Literal["cao", "vừa", "thấp", "không đủ dữ liệu"]
```

**Thứ tự field quan trọng**: `answer` đầu tiên để stream `token` ra ngay, còn
`used_chunk_ids`/`confidence` về ở cuối → validate sau khi answer đã stream xong (xem
Streaming). Node emit `token` cho mỗi delta của `answer`.

Prompt gồm **2 khối riêng** — đây là điểm cốt lõi của graph-as-content:

```
[ĐOẠN TÀI LIỆU]
chunk_id: lichsu_clean-000042
heading: II. Phong trào Cần Vương > 2.1. Trương Định
---
<nội dung chunk>

...

[QUAN HỆ ĐÃ BIẾT TỪ KNOWLEDGE GRAPH]
- Trương Định -[lãnh đạo]-> Phong trào kháng Pháp Nam Kỳ
  Mô tả: Trương Định không tuân lệnh bãi binh của triều đình, tiếp tục
  lãnh đạo nghĩa quân kháng Pháp ở Nam Kỳ, được tôn làm Bình Tây Đại Nguyên Soái.
  (nguồn: lichsu_clean-000041, 000042)
- Trương Định -[hy sinh tại]-> Gò Công
  Mô tả: Ngày 20/8/1864 căn cứ Gò Công bị bao vây, Trương Định tự sát.
  (nguồn: lichsu_clean-000043)
...
```

Mỗi graph item render đủ 3 phần: cạnh `source -[keyword]-> target`, `description` (nội
dung đã chưng cất xuyên chunk — **đây mới là phần giá trị**, không phải chỉ tên cạnh), và
`source_chunk_ids` làm nguồn. `description` lấy từ `GraphContextItem.description` (xem
`retrieval-layer-plan.md`). LLM được yêu cầu dùng cả hai khối làm nguồn, citation trỏ về
`chunk_id`.

Prompt rules:

- Chỉ trả lời dựa trên nội dung 2 khối trên.
- Nếu không đủ: `confidence = "không đủ dữ liệu"`, không bịa.
- Không đưa fact không có trong context.
- Mỗi claim chính phải có ít nhất một `used_chunk_id`.
- Trả lời tiếng Việt, giọng rõ ràng cho giáo viên/học sinh.

**Retry prompt**: tại lúc vào node, nếu `synthesize_attempt_count > 0` (đây là lượt thử
thứ 2+), append thêm vào cuối prompt:

```
LƯU Ý: Lượt tạo trước bị từ chối vì câu trả lời không có trích dẫn chunk_id hợp lệ.
Lần này hãy đảm bảo mỗi ý chính đều kèm chunk_id lấy từ danh sách [ĐOẠN TÀI LIỆU]
ở trên. Không được dùng chunk_id không có trong danh sách đó.
```

LLM với cùng prompt thường lặp lại cùng lỗi — thêm context về lý do thất bại giúp
model điều chỉnh output thay vì sinh lại y chang lượt trước.

Cuối node, **tăng `synthesize_attempt_count` lên 1** (đếm sau mỗi lần synthesize).

### 6. `validate_citations`

Server-side mandatory:

```text
LLM used_chunk_ids
  -> filter id in retrieved_chunk_ids (gồm cả citation chunk từ rule-B)
  -> dedupe
  -> build Citation from metadata
  -> nếu answer có nội dung nhưng citations rỗng:
       synthesize_attempt_count < synthesize_max_attempts -> retry synthesize
       synthesize_attempt_count >= synthesize_max_attempts -> honest_answer
```

Không cho citation tới chunk không nằm trong retrieval result.

Quote nếu có chỉ lấy đoạn ngắn từ chunk text, không bắt LLM tự bịa quote.

**Retry edge**: `validate_citations` → `synthesize` lặp tối đa tới `synthesize_max_attempts`
(mặc định 2 = 1 lần thử + 1 retry). `synthesize_attempt_count` trong state làm guard —
khởi tạo 0, node `synthesize` tăng lên 1 **sau mỗi** lần chạy. Sau synthesize lần 1:
count = 1, `1 < 2` → retry. Sau synthesize lần 2: count = 2, `2 < 2` sai → `honest_answer`,
không loop vô hạn.

**Khi `stream=True`**: nếu phải retry, answer của lượt 1 ĐÃ stream ra rồi → emit event
`regenerating` để frontend clear phần answer trước khi stream lượt 2. Đây là trường hợp
hiếm (0 citation hợp lệ), nhưng phải xử lý để không ghép 2 câu trả lời vào nhau.

### 7. `honest_answer`

Dùng khi:

- route `out_of_scope`
- retrieval trả về chunk rỗng
- citation validation fail sau retry

Ví dụ:

```text
Mình chưa tìm thấy đủ thông tin trong corpus hiện có để trả lời chắc chắn câu này.
Bạn có thể hỏi cụ thể hơn về nhân vật, mốc thời gian hoặc sự kiện không?
```

### 7b. `direct_response`

Dùng khi `route = "smalltalk"` — **không dùng chung `honest_answer`** vì message
"không đủ corpus" không phù hợp với lời chào hỏi.

Trả lời thân thiện ngắn gọn, không retrieve gì:

```text
"Xin chào"    → "Xin chào! Bạn muốn hỏi về sự kiện hoặc nhân vật lịch sử nào?"
"Cảm ơn bạn"  → "Không có gì! Bạn còn câu hỏi nào về lịch sử Việt Nam không?"
```

Có thể dùng template đơn giản hoặc LLM call nhỏ — không cần retrieval.

### 8. `clarify`

Kích hoạt khi `route = "ambiguous"` — câu hỏi có đại từ/chỉ định không rõ ("ông ấy",
"sự kiện đó", "trận đó") mà history không đủ để resolve.

Input:

- `question` + `history`

Output:

- `clarification_question`: câu hỏi làm rõ (LLM sinh hoặc template đơn giản)
- `clarification_needed = True`

Rules:

- Graph kết thúc **ngay sau node này**, không retrieve gì cả.
- Trả `AskResponse(clarification_needed=True, clarification_question="...")`.
- Frontend hiển thị câu hỏi → user trả lời → backend gửi request mới với history kèm
  câu trả lời đó → graph chạy lại bình thường từ `build_query`.
- **Không dùng `interrupt()`, không cần checkpointer** — graph thật sự kết thúc hoàn toàn.

Ví dụ:

```
User:  "Ông ấy đã làm gì sau đó?"
→ clarify: "Bạn đang hỏi về nhân vật nào ạ? (ví dụ: Hồ Chí Minh, Trương Định...)"

User:  "Trận đánh đó diễn ra như thế nào?"
→ clarify: "Bạn đang hỏi về trận đánh nào ạ?"
```

### 9. `build_visualization`

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
synthesize_max_attempts: int = 2     # tổng số lần synthesize (=2 → 1 lần thử + 1 retry)
stream_batch_chars: int = 160        # ngưỡng gom token thành batch trước khi emit (guardrails hook)
```

`synthesize_max_attempts` thay cho knob boolean cũ: một giá trị số điều khiển luôn số lần
synthesize. Retry edge dùng `synthesize_attempt_count < synthesize_max_attempts`. Đặt `= 1`
là tắt retry hoàn toàn, `= 2` là cho đúng 1 retry (mặc định).

`stream_batch_chars` quyết định độ "mịn" của stream: nhỏ → mượt hơn nhưng guardrails check
nhiều lần; lớn → ít overhead nhưng giật hơn. Batch cũng cắt ở dấu kết câu (xem Streaming).

Không thêm quá nhiều config trước khi có eval.

## Error handling API

Lỗi **trước khi stream bắt đầu** (validate request, dependency check sớm) trả HTTP status:

```text
422 - request validation error
503 - dependency unavailable: Qdrant/Neo4j/Postgres/OpenAI
504 - timeout
500 - unexpected bug, clean error body
```

Lỗi **sau khi SSE đã mở** (200 + byte đầu đã gửi) thì KHÔNG đổi được status code nữa →
phát qua event `error` rồi đóng stream:

```text
event: error
data: {"code": "synthesize_failed", "message": "..."}
```

`stream=False` thì map lại các code này về HTTP status như trên. Response lỗi không dump
stack trace hoặc secrets (cả HTTP body lẫn event `error`).

`/health`:

- process alive.

`/ready`:

- kiểm tra config cơ bản.
- optional lightweight ping Postgres/Qdrant/Neo4j/OpenAI nếu không quá chậm.

## Observability/debug

MVP log nên có:

- request id
- route decision (`needs_retrieval` / `ambiguous` / `out_of_scope` / `smalltalk`)
- số candidates vector + graph
- số chunks sau RRF/rerank
- số graph_context items
- used_chunk_ids
- warnings
- latency từng node

Nếu `debug=false`, response không trả debug chi tiết.

## Test plan

### Test diagram

```text
/ask
  -> validate request
  -> build_query (1 LLM call: rewrite + entity + route)
  -> route
      ├─ needs_retrieval -> retrieve
      ├─ ambiguous -> clarify -> END (trả clarification_question)
      ├─ out_of_scope -> honest_answer
      └─ smalltalk -> direct_response (thân thiện, không dùng chung honest_answer)
  -> retrieve (kèm seed_mentions)
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

- route `needs_retrieval` → gọi thẳng `retrieve_hybrid`, không switch mode.
- relation/cause/factual đều route `needs_retrieval`.
- ambiguous question (đại từ không rõ) -> clarify, không retrieve.
- bounded history validation rejects too long history.
- retrieve empty -> honest answer, no hallucinated citation.
- retrieval dependency error -> API 503.
- synthesize invalid `used_chunk_ids` -> filtered/dropped.
- synthesize `confidence == "không đủ dữ liệu"` + citation hợp lệ -> giữ answer và lời lưu ý.
- synthesize claims answer but no valid citations -> retry once -> honest fallback.
- `synthesize_attempt_count` guard: đúng 1 retry rồi dừng (tổng 2 lần synthesize).
- retry synthesize append chỉ dẫn lỗi vào prompt khi `attempt_count > 0`.
- citation metadata builds from chunk metadata.
- graph_context items (kèm description) rendered vào synthesize prompt.
- seed_mentions trích từ `standalone_query` đã rewrite (follow-up vẫn có seed).
- visualization builder receives validated `used_chunk_ids`.
- visualization builder error returns answer + warning.
- gazetteer empty/no markers still returns valid response.
- clarify response: clarification_needed=True, answer=None, citations rỗng, retrieval_mode="none".
- smalltalk -> direct_response, retrieval_mode="none".

### API tests

- `POST /ask` (stream=False) happy path with mocked retrieval + mocked LLM.
- `POST /ask` validation 422 for empty question.
- `POST /ask` history too large -> 422.
- `POST /ask` OpenAI timeout (stream=False) -> 504 or clean 503 depending exception mapping.
- `GET /health` returns alive.
- `GET /ready` returns dependency/config readiness.

### Streaming tests

- `stream=True` emit đúng thứ tự event: status* → token* → citations → visualization → done.
- token chỉ xuất hiện trong synthesize; answer ghép lại từ token == answer của stream=False.
- batch boundary: token gom tới dấu kết câu hoặc `stream_batch_chars` mới emit (không token thô).
- guardrails hook gọi trên MỖI batch trước khi emit (plan này hook là no-op, chỉ kiểm gọi đúng).
- hook chặn một batch -> emit `blocked`, dừng stream, batch sạch trước đó giữ nguyên.
- citations event chỉ về sau khi answer stream xong (thứ tự field đúng).
- 0 citation hợp lệ khi stream -> emit `regenerating` rồi stream lại (≤ max attempts).
- clarify khi stream -> emit `clarification` + `done`, KHÔNG có token.
- lỗi sau khi SSE mở -> event `error` (không phải đổi HTTP status), stream đóng sạch.
- `stream=False` gom event -> `AskResponse` tương đương kết quả stream.

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

1. ✅ Build retrieval layer (xong).
2. Thêm `get_async_openai_client()` vào `app/core/llm.py` (AsyncOpenAI).
3. Thêm `schemas/ask.py`: `ChatMessage`, `AskRequest`, `AskResponse`, `Citation`,
   `BuildQueryOutput`, `SynthesizedAnswer`, `RouteDecision`.
4. Thêm orchestrator state `AgentState` + nodes theo thứ tự flow:
   `build_query` → `route_intent` → `clarify` / `direct_response` / `retrieve` →
   `has_context` → `synthesize` → `validate_citations` → `honest_answer` →
   `build_visualization`.
5. Thêm synthesize prompt (2 khối: chunk text + graph_context), `answer` field đầu để stream.
6. Thêm FastAPI router `app/api/ask.py`: `/ask` (SSE + fallback `stream=False`), `/health`, `/ready`.
7. Hiện thực streaming: map `astream_events()` → SSE event (status/token/citations/
   visualization/clarification/regenerating/blocked/done/error); gom token thành batch +
   gọi guardrails hook (no-op) trước khi emit; collector cho `stream=False`.
8. Thêm tests với mocked retrieval/LLM/visualization (gồm streaming tests).
9. Thêm visualization integration.
10. Chạy ruff/mypy/pytest; tune theo eval set retrieval-plan.

## Acceptance criteria

- `/ask` trả answer tiếng Việt grounded bằng retrieved chunks.
- Citations luôn là subset của retrieved chunks (kể cả citation chunk từ rule-B).
- Câu mơ hồ (đại từ không rõ) → trả `clarification_question`, không retrieve, không bịa.
- `confidence == "không đủ dữ liệu"` + citation hợp lệ → giữ phần có căn cứ và lời lưu ý.
- `graph_context` (quan hệ KG) được render vào synthesize prompt — graph-as-content.
- `seed_mentions` từ `build_query` truyền xuống retrieval — zero LLM call thêm.
- Retry synthesize tối đa 1 lần; `synthesize_attempt_count` (`< 2`) guard chống loop.
- `retrieval_mode = "none"` cho clarify/smalltalk/out_of_scope; `"hybrid"` sau retrieve.
- Chỉ một chế độ retrieval: hybrid — không switch mode trong production.
- Smalltalk trả `direct_response` thân thiện, không dùng message "không đủ corpus".
- History bị giới hạn rõ ràng.
- `/ask` stream SSE mặc định: answer stream theo BATCH (qua guardrails hook), citations
  validate ở cuối, không retract (trừ hiếm 0-citation → `regenerating`); `stream=False`
  trả 1 JSON tương đương.
- Stream gom token thành batch + chừa guardrails hook (luật guardrails ở plan riêng).
- Lỗi sau khi SSE mở đi qua event `error`, không cố đổi HTTP status.
- Visualization không làm fail answer nếu thiếu marker/gazetteer.
- API lỗi dependency/timeout có status code sạch (ở chế độ stream=False / trước khi mở stream).
- Tests cover: happy path, streaming event order, clarification path, insufficient path,
  invalid citation path, dependency failure.

