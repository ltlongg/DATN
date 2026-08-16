# Plan: Index tài liệu từ UI admin (upload markdown → kho tri thức)

**Trạng thái:** 📝 Chưa code (viết plan 2026-08-07). Đây là "Bước 1" còn nợ lại từ Module 3
(danh mục tài liệu — "Bước 0" đã xong 2026-07-12).

Plan này gộp luôn 3 hạng mục dọn dẹp đã chốt trong lúc thiết kế: **xoá cascade**,
**provenance cấp chunk cho description trong KG**, và **bỏ cache đĩa của entity index**.
Ba thứ đó không phải "tiện tay làm thêm" — chúng là điều kiện cần để luồng index từ UI
chạy đúng, lý do ghi ở §8, §9, §10.

## 1. Mục tiêu

Cho admin đưa một tài liệu mới vào kho tri thức **hoàn toàn qua giao diện web**, thay vì
phải chạy 5 script CLI theo đúng thứ tự trên máy dev.

Trong phạm vi:

- Upload file `.md` (đã chuẩn hoá sẵn ngoài hệ thống).
- Màn preview cho đọc + sửa trực tiếp, gấp/mở theo heading.
- Chạy pipeline index có tiến độ, admin đóng trình duyệt vẫn chạy tiếp.
- Xoá tài liệu khỏi kho, sạch qua cả 4 store.
- Index lại một tài liệu (= xoá cascade rồi chạy lại).

**Ngoài phạm vi, cố ý:**

| Việc | Lý do |
|---|---|
| Upload PDF/DOCX, convert bằng Marker | Cắt theo quyết định 2026-08-07. Pipeline phụ thuộc cứng vào cấu trúc heading markdown; convert tự động cho ra text phẳng thì hỏng cả chunking lẫn phân unit timeline. Chuẩn hoá tài liệu là công đoạn ngoài hệ thống, có chủ ý. |
| Geocoding / `build_gazetteer.py` | Khâu toạ độ vẫn hoãn theo quyết định 2026-06-22. Địa danh cần người review từng cái, không nhét vào job tự động được. Timeline không phụ thuộc gazetteer. |
| Refactor `scripts/` để dùng chung `pipeline.py` | Đường offline là thứ duy nhất hiện dựng lại được kho tri thức. Không đụng nó trong lúc đang xây đường online. Gộp sau, khi online đã chứng minh chạy đúng. |
| Ước tính chi phí trước khi index | Cắt theo quyết định 2026-08-07 (màn preview đã đủ để quan sát). |

## 2. Quyết định đã chốt

| # | Quyết định | Lý do |
|---|---|---|
| 1 | Chỉ nhận `.md`, không convert | §1 |
| 2 | Backend sở hữu file `.md`; agent-service chỉ nhận **nội dung text** qua body | Backend là nơi phục vụ upload + preview + sửa. Agent-service không cần biết file nằm ở đâu → 2 service không phải chia sẻ volume, đúng với ranh giới đã có. |
| 3 | Trạng thái job ở **Postgres**, không dùng Redis | Tiến độ ~0,2 lượt/giây, Postgres thừa sức. Đổi lại được tính bền: service chết giữa chừng thì lúc khởi động lại còn biết job nào mồ côi. Redis để dành cho rate limit (món nợ đúng chỗ của nó). |
| 4 | Một job tại một thời điểm, toàn hệ thống | Job đốt LLM + GPU embedding trong **cùng process** đang phục vụ `/ask`. Chạy song song 2 job là tự bóp cổ đường trả lời. |
| 5 | Alias chạy **trước** merge Neo4j | `merge_graph` gọi `resolve()` lúc tạo khoá node. Build alias sau khi merge thì biến thể đã thành node riêng, phải re-merge mới sửa được. |
| 6 | Ghi DB **theo từng phase**, không gộp cuối | Một tài liệu lớn chạy 30–60 phút. Gộp mọi ghi vào cuối = lỗi ở phase cuối làm mất trắng phần trước. |
| 7 | Xoá cascade là **đồng bộ**, index là **job** | Xoá chỉ vài query, xong trong vài giây. Index mới cần job. |
| 8 | Phạm vi index: vector **bắt buộc**, graph + timeline là **checkbox** | Giữ nguyên hướng đã chốt 2026-07-12. Graph là pass đắt nhất. |

## 3. Luồng tổng thể

```text
admin upload .md
  → backend: cleaner.py → lưu file → document.status = 'draft'
  → admin xem preview, sửa, lưu (chỉ được ở 'draft')
  → admin chọn phạm vi (graph? timeline?) → bấm Index
  → backend POST /index sang agent-service (kèm nội dung markdown)
  → agent-service tạo index_job, chạy nền, trả job_id ngay

     phase 1  prepare    chunk Level 1-4                → (RAM)
     phase 2  metadata   LLM: times/actors/locations    → cache
     phase 3  store      rag_chunks + embed + Qdrant    ← checkpoint
     phase 4  graph      LLM: entity/quan hệ            → cache
     phase 5  alias      cập nhật alias_map (cặp mới)   ← checkpoint
     phase 6  merge      merge Neo4j                    ← checkpoint
     phase 7  timeline   segment + LLM/unit             ← checkpoint
     phase 8  finalize   reset entity index, đóng job

  → frontend poll 2s/lần, hiện phase + done/total
  → xong: document.status = 'indexed'
```

**Phase 2 (`metadata`) là bổ sung so với luồng bạn mô tả miệng** — nó không thể bỏ.
`CHUNK_VECTOR_META_FIELDS` trong [chunks.py](../../apps/agent-service/app/tools/graph_rag/chunks.py)
đưa `events/actors/times/locations` vào payload Qdrant, và payload đó được rerank dùng.
Bỏ phase này thì chunk mới vào kho sẽ nghèo metadata hơn hẳn 1213 chunk cũ — lệch âm thầm,
rất khó phát hiện qua UI.

Thứ tự phase 2 trước phase 3 là bắt buộc (payload phải đủ trước khi upsert vector), nhưng
`embedding_text` thì **không** phụ thuộc metadata — nó dựng từ heading + text ngay lúc chunk
([chunk_slicer.py:54](../../apps/agent-service/app/indexing/chunk_slicer.py#L54)).

## 4. Lưu trữ file + định danh

**Nơi lưu:** `DOCUMENTS_DIR` (env backend, mặc định `data/documents/`), mỗi tài liệu một file
`<document_id>.md`. Cần thêm volume trong compose để không mất khi rebuild container.

**`source_file` phải là ascii slug.** Đây là khoá nối xuyên hệ thống và
[`_chunk_id_prefix`](../../apps/agent-service/app/indexing/llm_chunker.py#L186) chỉ bỏ `.md`
rồi đổi `.` thành `_` — nên tên file tiếng Việt sẽ đẩy dấu và khoảng trắng thẳng vào
`chunk_id`, rồi từ đó vào payload Qdrant, `source_chunk_ids` của Neo4j và citation.

```python
def make_source_file(original_name: str, document_id: str) -> str:
    """'Lịch sử Việt Nam.md' -> 'lich-su-viet-nam-a1b2c3d4.md'"""
```

Slug hoá NFD + bỏ dấu + `[^a-z0-9]+` → `-`, cắt 40 ký tự, nối 8 ký tự đầu của `document_id`.
Hậu tố id giải quyết luôn chuyện hai lần upload cùng tên file đụng UNIQUE index trên
`documents.source_file`.

**INVARIANT: text được lưu = text được chunk.** `start_line`/`end_line` của chunk trỏ vào
đúng nội dung file. Cho nên:

1. `cleaner.py` chạy **một lần duy nhất**, ngay sau upload, trước khi admin nhìn thấy.
2. Bản admin bấm lưu ở màn preview là bản được đem đi chunk, không qua xử lý nào nữa.
3. Đã `indexed` thì file **đóng băng**. Muốn sửa → xoá cascade → index lại.

## 5. State machine của document

```text
     upload            admin bấm Index         job xong
none ────────→ draft ─────────────────→ indexing ────────→ indexed
                 ↑                          │                 │
                 │      job lỗi/gián đoạn   │                 │
                 └──────── failed ←─────────┘                 │
                 ↑                                            │
                 └──────── xoá cascade ───────────────────────┘
```

- **Sửa markdown chỉ cho phép ở `draft` và `failed`.** Ngoài ra 409.
- **Bấm Index chỉ cho phép ở `draft` và `failed`.**
- Từ `indexed` muốn sửa → bắt buộc đi qua xoá cascade (UI hỏi xác nhận, nói rõ sẽ phải
  index lại từ đầu và tốn LLM).

Bảng `documents` thêm cột (bảng backend tự quản → sửa thẳng `db.py`, drop tạo lại, không
cần ALTER migration):

```sql
ALTER TABLE documents ADD COLUMN IF NOT EXISTS original_name TEXT;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS last_job_id   UUID;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS index_scope   JSONB NOT NULL DEFAULT '{}'::jsonb;
```

`sync_kb_documents` giữ nguyên: nguồn nào đã có chunk trong kho mà chưa có document thì vẫn
tự hiện với `status='indexed'` (đường offline vẫn dùng được song song).

## 6. `index_jobs` — trạng thái job

Bảng do **agent-service** sở hữu DDL (cùng pattern `rag_chunks`, `timeline_events`), backend
đọc qua HTTP chứ không query thẳng.

```sql
CREATE TABLE IF NOT EXISTS index_jobs (
    job_id      UUID PRIMARY KEY,
    document_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    scope       JSONB NOT NULL DEFAULT '{}'::jsonb,
    status      TEXT NOT NULL,
    phase       TEXT,
    done        INTEGER NOT NULL DEFAULT 0,
    total       INTEGER NOT NULL DEFAULT 0,
    llm_calls   INTEGER NOT NULL DEFAULT 0,
    error       TEXT,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_index_jobs_doc
    ON index_jobs (document_id, started_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS idx_index_jobs_single_active
    ON index_jobs ((true)) WHERE status IN ('queued', 'running');
```

`status`: `queued | running | done | failed | interrupted`.
`phase`: `prepare | metadata | store | graph | alias | merge | timeline | finalize`.

**Cổng "một job tại một thời điểm" là unique index từng phần, không phải advisory lock.**
Advisory lock nhả ra khi session chết → hai process cùng nghĩ mình được chạy. Unique index
thì bền: job cũ còn `running` là job mới INSERT không vào được, trả 409 `index_busy`.

**Quét job mồ côi lúc khởi động.** Thêm vào `lifespan` của
[main.py](../../apps/agent-service/app/main.py) (chỗ đang warm-up model), chạy **trước** khi
nhận request:

```sql
UPDATE index_jobs
SET status = 'interrupted',
    error = 'Agent-service khởi động lại khi job đang chạy.',
    finished_at = now()
WHERE status IN ('queued', 'running');
```

Không có bước này thì service chết giữa job = tài liệu kẹt ở `indexing` vĩnh viễn và unique
index chặn luôn mọi job sau. Backend thấy `interrupted` thì đặt document về `failed`.

**Nhịp cập nhật tiến độ: throttle 1 giây**, không ghi mỗi chunk. `done/total` chỉ để hiển
thị, mất vài đơn vị cuối không sao.

## 7. `app/indexing/pipeline.py`

Lõi dùng chung, không biết gì về HTTP. Nhận callback tiến độ, trả kết quả. Test được không
cần FastAPI.

```python
@dataclass(frozen=True)
class IndexScope:
    graph: bool = True
    timeline: bool = True

@dataclass(frozen=True)
class PhaseProgress:
    phase: str
    done: int
    total: int

ProgressFn = Callable[[PhaseProgress], None]

@dataclass
class IndexResult:
    chunks: int
    vectors: int
    entities: int
    relations: int
    events: int
    llm_calls: int

def index_document(
    markdown: str,
    *,
    source_file: str,
    document_title: str,
    scope: IndexScope,
    on_progress: ProgressFn,
    workers: int = 4,
    cache_dir: Path | None = None,
) -> IndexResult:
    ...
```

Mỗi phase là một hàm rời, gọi được độc lập trong test:

```python
def phase_prepare(markdown: str, *, source_file: str, document_title: str) -> list[dict]
def phase_metadata(chunks: list[dict], *, on_progress, workers, cache: Path) -> list[dict]
def phase_store(records: list[dict], *, on_progress, batch_size: int = 128) -> tuple[int, int]
def phase_graph(records: list[dict], *, on_progress, workers, cache: Path) -> dict[str, GraphExtraction]
def phase_alias(extractions, *, frozen_canonicals: set[str]) -> int
def phase_merge(extractions, *, on_progress) -> tuple[int, int]
def phase_timeline(records: list[dict], *, on_progress, workers, cache: Path) -> int
def phase_finalize() -> None
```

**Cache resume: per-document, KHÔNG đụng artifact chung.**

```text
dataset/index_cache/<source_file>.metadata.json
dataset/index_cache/<source_file>.graph.json
dataset/index_cache/<source_file>.timeline.json
```

`dataset/chunks_llm.json` và `dataset/graph_extractions.json` là artifact của đường offline —
file 10MB dùng chung, ghi đè từ nhiều tiến trình là hỏng cả kho chunk của tài liệu khác.
Đường online tuyệt đối không ghi vào đó. Khoá cache và luật resume giữ nguyên như script
(`prompt_version` + `chunk_id`), chỉ đổi chỗ để file.

Ba cache này cho phép chạy lại job đã `failed` mà không trả tiền LLM lần hai cho phần đã
xong. Thêm cờ `--overwrite` tương đương ở API để ép trích lại.

`phase_finalize` gọi `reset_entity_index_cache()` rồi `get_entity_index()` để dựng lại ngay
trong job, thay vì để độ trễ rơi vào câu hỏi đầu tiên của người dùng.

## 8. Xoá cascade — `app/indexing/deletion.py`

Đang bị chặn cứng ở [documents.py:60](../../apps/backend/app/api/documents.py#L60) với 409
`document_indexed`. Đây là thứ mở khoá cả nút Xoá lẫn đường "sửa tài liệu đã index".

```python
def delete_document_from_stores(source_file: str) -> DeletionReport:
    """Gỡ mọi dấu vết của một nguồn khỏi Postgres + Qdrant + Neo4j."""
```

**Thứ tự bắt buộc** — `rag_chunks` xoá **cuối cùng**, vì nó là chỗ duy nhất tra ngược ra tập
`chunk_id`; xoá trước rồi lỗi giữa chừng là mất đường retry:

```text
1. SELECT chunk_id FROM rag_chunks WHERE metadata->>'source_file' = %s
2. Qdrant : delete points theo id = point_id_for(chunk_id)
3. Neo4j  : gỡ chunk_id khỏi Entity + REL, xoá cái mồ côi
4. Postgres timeline_events : gỡ chunk_id, xoá dòng rỗng
5. Postgres rag_chunks : DELETE
6. reset_entity_index_cache()
```

Qdrant (point id tất định, [vector_store.py:66](../../apps/agent-service/app/tools/graph_rag/vector_store.py#L66)):

```python
client.delete(
    collection_name=settings.qdrant_collection,
    points_selector=PointIdsList(points=[point_id_for(cid) for cid in chunk_ids]),
)
```

Neo4j, entity (relation làm y hệt với `MATCH ()-[r:REL]->()`):

```cypher
MATCH (e:Entity) WHERE any(c IN e.source_chunk_ids WHERE c IN $chunk_ids)
WITH e, [i IN range(0, size(e.desc_chunk_ids) - 1)
         WHERE NOT e.desc_chunk_ids[i] IN $chunk_ids] AS keep
SET e.descriptions     = [i IN keep | e.descriptions[i]],
    e.desc_chunk_ids   = [i IN keep | e.desc_chunk_ids[i]],
    e.source_chunk_ids = [c IN e.source_chunk_ids WHERE NOT c IN $chunk_ids]
WITH e WHERE size(e.source_chunk_ids) = 0
DETACH DELETE e
```

**Chỉ xoá node mồ côi.** "Hồ Chí Minh" xuất hiện ở 164 chunk trải nhiều tài liệu — gỡ một
tài liệu mà xoá phăng node là phá KG của các tài liệu còn lại.

`timeline_events` (cùng nguyên tắc mồ côi):

```sql
UPDATE timeline_events
SET source_chunk_ids = COALESCE(
        (SELECT array_agg(c) FROM unnest(source_chunk_ids) AS c
         WHERE NOT (c = ANY(%(ids)s::text[]))),
        '{}'::text[])
WHERE source_chunk_ids && %(ids)s::text[];

DELETE FROM timeline_events WHERE cardinality(source_chunk_ids) = 0;
```

`gazetteer` **không đụng** — key theo tên địa danh, dùng chung mọi tài liệu, và toạ độ đắt.

`DeletionReport` trả về số lượng từng store để hiện lên UI và ghi vào log.

## 9. Provenance cấp chunk cho description trong KG

**Vấn đề.** Ở [graph_store.py:44](../../apps/agent-service/app/tools/graph_rag/graph_store.py#L44),
`descriptions` và `source_chunk_ids` là hai mảng dedup **độc lập**, không thẳng hàng theo
index. Hệ quả:

1. Xoá tài liệu gỡ được `chunk_id` nhưng **không biết description nào thuộc chunk đó** →
   node sống sót mang theo mô tả sinh ra từ tài liệu đã xoá. Sai âm thầm.
2. [`GraphContextItem.description`](../../apps/agent-service/app/schemas/retrieval.py#L79) là
   một chuỗi gộp, `source_chunk_ids` là list rời bên cạnh → **mọi câu trong câu trả lời sinh
   ra từ tri thức đồ thị hiện không cite chính xác về chunk nào**. Cái này đáng giá hơn
   chuyện xoá.

**Không dùng được `contributions: [{chunk_id, description}]`** — property của Neo4j chỉ nhận
primitive hoặc mảng primitive, không nhận mảng map. Cách đúng là **hai mảng song song, giữ
thẳng hàng theo index**:

```text
e.descriptions   = ["mô tả A", "mô tả B", ...]
e.desc_chunk_ids = ["lichsu_clean_012", "lichsu_clean_045", ...]
```

Luật merge đổi: append **cả cặp cùng lúc**, idempotent theo cặp `(chunk_id, description)`.
Hai chunk mô tả giống hệt nhau thì giữ hai dòng — mỗi dòng một nguồn; dedup để hiển thị làm
lúc đọc, không làm lúc ghi.

```cypher
UNWIND $entities AS ent
MERGE (e:Entity {norm_name: ent.norm_name})
ON CREATE SET e.name = ent.name,
              e.type = ent.type,
              e.descriptions     = [ent.description],
              e.desc_chunk_ids   = [$chunk_id],
              e.source_chunk_ids = [$chunk_id]
ON MATCH SET e.name = coalesce(e.name, ent.name),
             e.type = coalesce(e.type, ent.type),
             e.descriptions = CASE
                 WHEN any(i IN range(0, size(e.descriptions) - 1)
                          WHERE e.descriptions[i] = ent.description
                            AND e.desc_chunk_ids[i] = $chunk_id)
                 THEN e.descriptions ELSE e.descriptions + ent.description END,
             e.desc_chunk_ids = CASE
                 WHEN any(i IN range(0, size(e.descriptions) - 1)
                          WHERE e.descriptions[i] = ent.description
                            AND e.desc_chunk_ids[i] = $chunk_id)
                 THEN e.desc_chunk_ids ELSE e.desc_chunk_ids + $chunk_id END,
             e.source_chunk_ids = CASE WHEN $chunk_id IN e.source_chunk_ids
                 THEN e.source_chunk_ids ELSE e.source_chunk_ids + $chunk_id END
```

**INVARIANT:** `size(e.descriptions) = size(e.desc_chunk_ids)` với mọi node và mọi cạnh.
Viết một test chạy Cypher kiểm tra invariant này trên toàn KG sau khi merge.

**Thay đổi thuần cộng.** `entity_index` vẫn đọc `size(e.source_chunk_ids)`, `search_graph`
vẫn đọc `descriptions` như cũ. Sửa xong mà chưa kịp dùng mapping thì hệ thống chạy y nguyên.
Tận dụng mapping để cite graph context là việc riêng, làm sau, không thuộc plan này.

### 9.1 Migration — gộp luôn với việc sửa alias_map đang cũ

Node cũ không có `desc_chunk_ids` nên phải dựng lại KG. Nhân dịp đó sửa luôn một lỗi dữ
liệu phát hiện ngày 2026-08-07:

`alias_seed.json` (mtime 28/07 20:42) **mới hơn** `alias_map.json` (28/07 19:08), và không
một key nào của các cụm seed có mặt trong map — `nguyễn ái quốc`, `nguyễn tất thành`,
`bác hồ`, `sài gòn` đều trượt. Nghĩa là cụm thủ công
`['Hồ Chí Minh', 'Nguyễn Ái Quốc', 'Nguyễn Tất Thành', 'Bác Hồ', 'Chủ tịch Hồ Chí Minh']`
chưa bao giờ được áp. Hiện KG có `nguyễn ái quốc` là node riêng với `source_count = 4`,
tách khỏi `hồ chí minh` (`source_count = 164`). Hỏi về "Nguyễn Ái Quốc" thì GraphRAG seed
vào node 4 chunk — đúng cái mà alias resolution sinh ra để tránh.

`graph_extractions.json` (31/07) còn mới hơn cả hai → map cũ so với KG hai lớp.

Chạy một lượt, **không tốn API** (verdict cache theo cặp, extraction cache đã đủ):

```powershell
$env:PYTHONIOENCODING="utf-8"
cd "d:\Đồ án\DATN\apps\agent-service"

# 1. dựng lại alias_map (chỉ trả tiền cho cặp ứng viên mới)
.\venv\Scripts\python.exe scripts\build_alias_map.py --workers 8

# 2. xoá KG (CHỈ Neo4j — không đụng rag_chunks/Qdrant)
#    reset_stores.py hiện xoá cả 3 store -> thêm cờ --only neo4j trước khi chạy

# 3. merge lại từ cache, với schema desc_chunk_ids mới
.\venv\Scripts\python.exe scripts\run_graph_index.py --limit 0 --skip-vectors --remerge
```

Bước 2 cần sửa nhỏ: [reset_stores.py](../../apps/agent-service/scripts/reset_stores.py) hiện
xoá cả Postgres + Qdrant + Neo4j. Thêm `--only neo4j`. Đây là ngoại lệ duy nhất được phép
với luật "không đụng `scripts/`" ở §1 — và là thêm cờ, không đổi hành vi mặc định.

Sau bước 3: xoá `dataset/entity_index.json` (§10) và khởi động lại agent-service.

## 10. Bỏ cache đĩa của entity index

`dataset/entity_index.json` là cache thuần dẫn xuất từ Neo4j + `alias_map.json`. Đo thật
trên file hiện tại: **5.646 node = 1,65 MB RAM** (đã tính cả chuỗi tên) — không đáng kể cạnh
model embedding + reranker + BM25 đang thường trú cùng process.

Cache đó chỉ tiết kiệm được lần dựng đầu tiên sau mỗi lần restart, mà vẫn phải bắn một query
COUNT để kiểm version. Đổi lại nó gánh một bug tiềm ẩn: `kg_version` = **số node**, nên xoá
một tài liệu rồi index lại ra đúng chừng ấy node là version trùng → dùng cache cũ, ground
về entity đã xoá. Với luồng index/xoá mới, kịch bản đó không còn hiếm.

Sửa [entity_index.py](../../apps/agent-service/app/tools/graph_rag/entity_index.py) — **đúng
một file**, grep cả `app/`, `tests/`, `scripts/` chỉ thấy `get_entity_index` được dùng bên
ngoài, tại [graph_store.py:188](../../apps/agent-service/app/tools/graph_rag/graph_store.py#L188)
và [:256](../../apps/agent-service/app/tools/graph_rag/graph_store.py#L256):

- Bỏ: `_DEFAULT_CACHE`, `entity_index_path()`, `_write_cache()`, `to_cache_dict()`,
  `_alias_map_version()`, `_kg_version()`, `_current_versions()`, `_COUNT_ENTITIES`.
- `load_entity_index()` rút còn phần gọi `build_entity_index()`.
- Giữ `build_entity_index`, `get_entity_index` (`lru_cache`), `reset_entity_index_cache`.
- Thêm `get_entity_index()` vào warm-up trong `lifespan` — dời độ trễ ra khỏi câu hỏi đầu
  tiên, và lộ sớm nếu Neo4j chết.
- Xoá file `dataset/entity_index.json` (đang untracked, xoá là xong).

Còn khoảng 60 dòng biến mất. Việc làm mới index về **một cơ chế duy nhất và trung thực**:
`reset_entity_index_cache()`, do `phase_finalize` và `delete_document_from_stores` gọi.

## 11. Contract API

### 11.1 Agent-service (gác `verify_internal_key`, router mới `app/api/index.py`)

```
POST   /index
       body: {document_id, source_file, document_title, markdown, scope:{graph,timeline}}
       201 {job_id}
       409 index_busy      — đang có job khác chạy
       422 no_headings     — parse_sections trả 0 section

GET    /index/jobs/{job_id}
       200 {job_id, document_id, status, phase, done, total, llm_calls, error,
            started_at, updated_at, finished_at}

GET    /index/jobs?document_id=...&limit=20
       200 [ ... ]   — lịch sử, cho admin xem lần index trước tốn bao lâu

DELETE /index/documents/{source_file}
       200 {chunks, vectors, entities_deleted, relations_deleted, events_deleted}
       — ĐỒNG BỘ, không tạo job
```

Cổng `422 no_headings` là chốt chặn rẻ duy nhất còn lại sau khi bỏ dry-run: file markdown
không có heading nào thì `parse_sections` trả 0 section, toàn bộ văn bản rơi xuống Level 4
cho SlumberChunker cắt bằng LLM — vừa đắt vừa cho chunk kém, `heading_path` rỗng thì hỏng cả
citation lẫn phân unit timeline. Chặn ở cửa, không để chạy 30 phút rồi mới biết.

Chạy nền: `anyio.to_thread.run_sync` trong `BackgroundTasks`. Pipeline là code đồng bộ
(psycopg, driver Neo4j, LLM client blocking) — chạy thẳng trên event loop là chặn `/ask`.

### 11.2 Backend (`app/api/documents.py`)

```
POST   /api/admin/documents/upload        multipart, chỉ .md → 201 DocumentOut (draft)
GET    /api/admin/documents/{id}/markdown → 200 {markdown, editable}
PUT    /api/admin/documents/{id}/markdown → 200 OkResponse   (409 nếu không ở draft/failed)
POST   /api/admin/documents/{id}/index    body {scope} → 202 {job_id}
GET    /api/admin/documents/{id}/index-status → 200 (proxy sang agent)
DELETE /api/admin/documents/{id}          → cascade rồi xoá row (bỏ chặn 409 cũ)
```

`agent_client.py` thêm: `start_index()`, `get_index_job()`, `delete_document_from_kb()`.

Backend **không tự chạy pipeline** — nguyên tắc cũ giữ nguyên: mọi logic LLM/retrieval nằm
trong agent-service, backend chỉ là gateway.

## 12. Frontend

- `api/documents.ts` — 6 endpoint mới.
- `features/admin/DocumentUpload.tsx` — dropzone, chỉ nhận `.md`.
- `features/admin/MarkdownEditor.tsx` — CodeMirror 6 + `@codemirror/lang-markdown`, bật
  `foldGutter` với luật fold theo dòng heading (`#`), đúng như trong VS Code. Một khung, sửa
  trực tiếp, nút Lưu.
- `features/admin/IndexProgress.tsx` — phase + thanh `done/total`, poll 2s bằng TanStack
  Query `refetchInterval`, dừng poll khi `status` chuyển sang trạng thái kết thúc.
- `AdminDocumentsPage.tsx` + `useDocuments.ts` — nối vào, thêm mutation upload/index/xoá.

**Ngưỡng cảnh báo kích thước ~500KB**: trên ngưỡng thì khuyên tải về sửa ngoài rồi upload
lại, đừng để có ngày admin mở `lichsu.clean.md` 3,1MB lên rồi trình duyệt đứng hình.

## 13. Ba lát cắt triển khai

Mỗi lát tự chạy được và verify được ngay. Không lát nào làm hỏng hệ thống đang chạy.

### Lát 1 — xoá cascade + `desc_chunk_ids` (§8, §9, §10)

Chỉ agent-service, không đụng frontend, không có job, không có HTTP mới ngoài `DELETE`.

Verify:

1. Chạy migration §9.1, kiểm invariant `size(descriptions) = size(desc_chunk_ids)` trên
   toàn KG.
2. Kiểm alias đã ăn: `nguyễn ái quốc` phải resolve về `hồ chí minh`, và node
   `nguyễn ái quốc` không còn tồn tại riêng.
3. Xoá `tap1.clean.md` khỏi 4 store → đếm lại: `rag_chunks` giảm đúng số chunk của nguồn đó,
   Qdrant giảm đúng chừng ấy point, `timeline_events` không còn dòng rỗng, KG **không** mất
   node dùng chung với `lichsu.clean.md`.
4. `run_graph_index.py --remerge` dựng lại → về đúng số cũ.

Xong lát này: nút Xoá trong UI hết chết.

### Lát 2 — job + pipeline, chưa có UI

`pipeline.py`, `jobs.py`, `api/index.py`, quét job mồ côi lúc khởi động. Gọi bằng curl với
một file `.md` cắt nhỏ (~30–50KB, một chương từ `phi-su-kien.clean.md`) để không đốt tiền.

Verify — toàn bộ phần khó nằm ở đây, và không cần một dòng React nào:

1. Chạy hết 8 phase, `GET /index/jobs/{id}` phản ánh đúng phase + tiến độ.
2. Gọi `POST /index` lần hai lúc đang chạy → 409 `index_busy`.
3. Giết agent-service giữa phase `graph`, khởi động lại → job thành `interrupted`, job mới
   INSERT được.
4. Chạy lại job vừa gián đoạn → phase `metadata`/`graph` ăn cache, không gọi LLM lại.
5. Upload file không có heading → 422 `no_headings`, không tốn đồng nào.
6. Index xong → xoá cascade → index lại → số liệu 4 store về đúng như lần đầu.
7. Trong lúc job chạy, `/ask` vẫn trả lời được (chậm hơn là chấp nhận được, treo thì không).

### Lát 3 — upload + editor + màn tiến độ

Backend routes + frontend. Lúc này phần lõi đã đúng, frontend chỉ là vỏ.

## 14. Cạm bẫy đã biết

| # | Bẫy | Cách chặn |
|---|---|---|
| 1 | `replace_timeline_events` **TRUNCATE cả bảng** ([event_store.py:114](../../apps/agent-service/app/tools/visualization/event_store.py#L114)) — index một tài liệu là xoá sạch event của mọi tài liệu khác | Thêm `upsert_timeline_events()` theo phạm vi `chunk_id` của đúng tài liệu. **Giữ nguyên** `replace_timeline_events` cho script offline. |
| 2 | Alias canonical **lật** khi thêm tài liệu — `build_alias_map` chọn canonical theo số lần nhắc, tài liệu mới đổi số đếm → canonical đổi, trong khi Neo4j giữ node dưới canonical cũ → tách đôi thực thể | `phase_alias` nhận `frozen_canonicals` = tập `norm_name` đã có node trong KG, khoá cứng canonical của các cụm đó; chỉ cụm hoàn toàn mới được tự chọn. |
| 3 | `get_entity_index` là `lru_cache` **theo process** — job merge xong, RAM vẫn giữ index cũ tới lúc restart | `phase_finalize` và `delete_document_from_stores` bắt buộc gọi `reset_entity_index_cache()`. |
| 4 | Job đốt LLM + GPU trong **cùng process** phục vụ `/ask` | Một job tại một thời điểm (§6) + `workers` mặc định 4, cho chỉnh qua body. |
| 5 | Level 4 `SlumberChunker` gọi LLM khi gặp section quá lớn → chi phí bất ngờ không ai lường | Đếm `stats.level4_calls` từ `ChunkStats`, ghi vào `index_jobs.llm_calls` và hiện lên UI. |
| 6 | Sửa markdown sau khi đã index → `start_line/end_line` của chunk trỏ sai chỗ, citation lệch âm thầm | File đóng băng ở `indexed` (§5). Muốn sửa phải đi qua xoá cascade. |
| 7 | Tên file tiếng Việt → dấu và khoảng trắng lọt vào `chunk_id` rồi lan khắp 4 store | Ascii slug + hậu tố `document_id` (§4). |
| 8 | Đường online ghi vào `chunks_llm.json` / `graph_extractions.json` → hỏng kho chunk của tài liệu khác | Cache per-document trong `dataset/index_cache/` (§7). Bất biến của plan này. |

## 15. Nợ lại sau plan

- **Tận dụng `desc_chunk_ids` để cite graph context.** Schema có rồi nhưng
  `GraphContextItem` vẫn gộp description thành một chuỗi. Sửa để mỗi mô tả kèm nguồn là một
  điểm cộng thật cho phần đánh giá — làm sau, plan riêng.
- **Gộp `scripts/` về dùng chung `pipeline.py`.** Chỉ làm khi đường online đã chạy đúng qua
  vài tài liệu thật.
- **Geocoding.** Vẫn hoãn.
- **Upload PDF/DOCX.** Nếu sau này làm, đường đi là convert → `cleaner` → đúng màn preview
  đã có ở plan này, không phải xây lại gì.

## 16. Trạng thái triển khai

| Lát | Hạng mục | Trạng thái |
|---|---|---|
| — | Viết plan | ✅ 2026-08-07 |
| 1 | `desc_chunk_ids` + migration §9.1 | ⬜ |
| 1 | `deletion.py` + `DELETE /index/documents/{source_file}` | ⬜ |
| 1 | Bỏ cache đĩa entity index | ⬜ |
| 2 | `pipeline.py` 8 phase | ⬜ |
| 2 | `index_jobs` + quét job mồ côi | ⬜ |
| 2 | `api/index.py` | ⬜ |
| 2 | `upsert_timeline_events` | ⬜ |
| 3 | Backend routes + `agent_client` | ⬜ |
| 3 | Frontend upload + editor + tiến độ | ⬜ |
