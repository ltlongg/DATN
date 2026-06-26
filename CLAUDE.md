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

## Repository Status

Repo là **git repository** (branch `main`). Không còn ở scaffold stage:

- **`agent-service`**: đã có pipeline indexing thực (preprocessing → chunking → graph extraction → timeline extraction → geocoding). Đây là nơi tập trung gần như toàn bộ code hiện tại. Phần `api/` (FastAPI routes) và `orchestrator/` (LangGraph) **chưa build** — retrieval/answer flow là việc kế tiếp.
- **`backend`** và **`frontend`**: vẫn ở scaffold (cấu trúc thư mục + config, chưa có code thực). Khi thêm file, tuân theo cấu trúc đã có (xem Architecture).

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

**Nguyên tắc quan trọng**: backend KHÔNG trực tiếp là agent. Backend chỉ là API gateway gọi sang `agent-service` qua HTTP client (`apps/backend/app/modules/agent_client/`). Mọi logic LLM/retrieval nằm trong `agent-service`.

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
- `tools/graph_rag/` — `chunk_store.py` (Postgres), `vector_store.py` (Qdrant), `graph_store.py` (Neo4j).
- `tools/visualization/` — `event_store.py` (`timeline_events`), `gazetteer_store.py` (`gazetteer`), `builder.py` (online).
- `prompts/` — prompt templates có versioning (graph_extract, metadata_extract, timeline_extract, geocode, alias_judge).
- `schemas/` — Pydantic models (chunk, graph, metadata, timeline, gazetteer, visualization, alias).
- `core/` — config, llm, embedding, clients (qdrant, neo4j).
- `scripts/` — CLI utilities (xem Commands).
- `api/`, `orchestrator/`, `tools/traditional_rag/`, `tools/hybrid/` — **chưa build** (kế hoạch theo Architecture; retrieval/answer flow là việc kế tiếp).

### Backend internal layout (`apps/backend/app/`) — scaffold
- `modules/auth` — JWT, 2 roles: `admin` và `teacher`
- `modules/documents` — CRUD tài liệu (MVP có thể mock)
- `modules/rag` — endpoint hỏi đáp, gọi sang agent-service
- `modules/visualization` — trả map data + timeline data cho frontend
- `modules/agent_client` — httpx client gọi agent-service
- `modules/users`, `core/`, `db/`, `shared/` — chuẩn

### Frontend layout (`apps/frontend/src/`) — scaffold
- `features/chat` — UI hỏi đáp
- `features/map` — bản đồ Việt Nam, markers cho events (xem POC Google Maps bên dưới)
- `features/timeline` — timeline events liên kết với map qua `event_id`
- `features/admin` — quản lý documents
- `features/auth` — đăng nhập

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
Dùng **root venv** (`.\venv\Scripts\python.exe`) — `apps/agent-service/venv` trống, không có deps. Cả backend và agent-service dùng `ruff`, `mypy`, `pytest` (đã có trong root venv):
```powershell
.\venv\Scripts\python.exe -m ruff check apps/agent-service/app
.\venv\Scripts\python.exe -m mypy apps/agent-service/app
.\venv\Scripts\python.exe -m pytest apps/agent-service/tests                # toàn bộ
.\venv\Scripts\python.exe -m pytest apps/agent-service/tests/test_foo.py::test_bar  # 1 test
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
- `docs/plan/` — plan đã duyệt: `chunking-embedding-plan.md` (lý do gỡ LightRAG + DIY pipeline), `llm-chunking-plan.md`, `timeline-map-plan.md` (source-of-truth timeline/map), `lichsu-headings.md`.
- `docs/reference/google-maps-api.md` — tham chiếu Google Geocoding/Maps + ToS caching.
- `docs/design/frontend-scope.md`, `docs/brainstorming/` — scope frontend + session notes kiến trúc.
