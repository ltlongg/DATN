# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Context

Đồ án tốt nghiệp: **Agentic RAG cho lịch sử Việt Nam** (giai đoạn Pháp thuộc → thống nhất đất nước), dành cho giáo viên. Hệ thống hỏi đáp tiếng Việt có căn cứ từ tài liệu, kết hợp **traditional RAG + GraphRAG + hybrid retrieval**, có khả năng render câu trả lời lên **bản đồ Việt Nam + timeline** khi sự kiện có dữ liệu thời gian/địa điểm.

Dataset chính: `lichsu.md` (~3MB text thuần, ~2.36M ký tự, 6.878 dòng) — chưa được index. Communication và code comments dùng tiếng Việt là OK theo phong cách dự án.

## Nguyên tắc phát triển

**Tra docs trước, code sau.** Trước khi viết bất kỳ thuật toán/logic nào, **bắt buộc web search** tài liệu chính thức của thư viện liên quan để nắm đủ API hiện có. Không được giả định thư viện chỉ làm được những gì mình đã thấy trong code — thư viện thường có nhiều tính năng hơn. Ví dụ: Chonkie không chỉ có `RecursiveChunker` mà còn có nhiều chunker, tokenizer, pipeline utilities khác.

**Ưu tiên thư viện sẵn có, không code tay lại từ đầu.** Sau khi đã tra docs, kiểm tra xem các thư viện đã có trong stack có làm được không:

- **Chunking**: dùng `Chonkie` (`RecursiveChunker`, `RecursiveRules`, `min_characters_per_chunk`). Không tự code greedy merge, sliding window, hay sentence splitter.
- **Orchestration / agentic flow**: dùng `LangGraph` (`StateGraph`, `Send`, `Command`). Không tự code state machine hay retry loop.
- **Retrieval / vector search**: dùng `Qdrant` client trực tiếp. Không tự implement ANN hay re-ranking từ đầu.
- **Graph queries**: dùng `Neo4j` driver + Cypher. Không tự implement graph traversal.
- **HTTP async**: dùng `httpx`. Không dùng `requests` trong async context.
- **Schema validation**: dùng `Pydantic`. Không tự viết dict validation.

Nếu thư viện hiện có không đủ → ghi rõ lý do trước khi viết custom code. "Tôi không nhớ API" không phải lý do — đọc docs hoặc hỏi.

## Repository Status

Repo hiện đang ở **scaffold stage**: cấu trúc thư mục đã tạo, `requirements.txt` và `docker-compose.yml` đã cấu hình, nhưng **chưa có code Python/TS thực** trong `apps/*/app/` hoặc `apps/frontend/src/`. Khi thêm file đầu tiên, tuân theo cấu trúc thư mục đã có sẵn (xem section Architecture).

Repo **không phải git repository** (`git_repo: false`). Không chạy `git init` trừ khi user yêu cầu rõ ràng.

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

### Storage roles
- **Postgres**: users, documents metadata, conversation logs
- **Qdrant** (collection `history_vn_chunks`): vector embeddings cho RAG truyền thống
- **Neo4j** (+ APOC plugin): knowledge graph cho GraphRAG (entities: Nhân vật, Sự kiện, Địa điểm, Tổ chức, Giai đoạn, Nguyên nhân, Hệ quả)
- **Redis**: cache + lightweight queue

### Agent-service internal layout (`apps/agent-service/app/`)
- `api/` — FastAPI routes nhận request từ backend
- `orchestrator/` — LangGraph state machine quyết định route (RAG / GraphRAG / hybrid), phân tích intent, tổng hợp answer
- `tools/traditional_rag/`, `tools/graph_rag/`, `tools/hybrid/` — 3 retrieval strategies, agent chọn 1 hoặc kết hợp
- `indexing/preprocessing/` — chuẩn hóa text trước khi chunk (heading, dash, quote, ellipsis, tách paragraph dài). Idempotent + non-destructive
- `prompts/` — prompt templates (cần versioning)
- `schemas/` — Pydantic models cho request/response
- `core/` — config, logging, clients (Qdrant, Neo4j, LLM)
- `scripts/` — CLI utilities (ví dụ `preprocess_dataset.py`)

### Backend internal layout (`apps/backend/app/`)
- `modules/auth` — JWT-based, 2 roles: `admin` và `teacher`
- `modules/documents` — CRUD tài liệu (MVP có thể mock, sau hỗ trợ PDF/DOCX/TXT upload)
- `modules/rag` — endpoint hỏi đáp, gọi sang agent-service
- `modules/visualization` — trả map data + timeline data cho frontend
- `modules/agent_client` — httpx client gọi agent-service
- `modules/users`, `core/`, `db/`, `shared/` — chuẩn

### Frontend layout (`apps/frontend/src/`)
- `features/chat` — UI hỏi đáp
- `features/map` — bản đồ Việt Nam, markers cho events (tham khảo POC tại `trackasia-map-test.html` ở root)
- `features/timeline` — timeline events liên kết với map qua `event_id`
- `features/admin` — quản lý documents
- `features/auth` — đăng nhập

### Visualization contract (quan trọng)
Map và timeline phải dùng **chung `event_id`** để liên kết hai chiều (click marker → highlight timeline item và ngược lại). Quy tắc:
- Event thiếu địa điểm → chỉ hiển thị timeline
- Event thiếu thời gian → chỉ hiển thị map
- Không đủ data → KHÔNG ép sinh marker; honest về uncertainty
- Visualization data sinh ra **online từ events đã retrieve**, KHÔNG pre-compute theo câu hỏi. Metadata (time/location/lat/lon/confidence) phải được extract **offline** khi indexing document.

## Commands

### Run toàn bộ stack (Docker Compose)
```bash
# Từ project root
cp .env.example .env  # rồi điền OPENAI_API_KEY, NEO4J_PASSWORD, ...
docker compose -f infra/compose/docker-compose.yml up -d
```
Services lên: postgres :5432, qdrant :6333, neo4j :7474/7687, redis :6379, backend :8000, agent-service :9000, frontend :5173.

### Chạy local (không docker)
Mỗi service dùng venv riêng — `apps/agent-service/venv/` đã tồn tại, `apps/backend/` cần tạo riêng.

```powershell
# Agent-service
cd apps/agent-service
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 9000 --reload

# Backend
cd apps/backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Frontend (sau khi scaffold Vite)
cd apps/frontend
npm install
npm run dev
```

### Lint / typecheck / test (Python services)
Dùng **root venv** (`.\venv\Scripts\python.exe`) — `apps/agent-service/venv` trống, không có deps.
Cả backend và agent-service dùng `ruff`, `mypy`, `pytest` (đã có trong root venv):
```powershell
.\venv\Scripts\python.exe -m ruff check apps/agent-service/app
.\venv\Scripts\python.exe -m mypy apps/agent-service/app
.\venv\Scripts\python.exe -m pytest apps/agent-service/tests                # toàn bộ
.\venv\Scripts\python.exe -m pytest apps/agent-service/tests/test_foo.py::test_bar  # 1 test
```

### Chunking experiment
`test.py` ở root là script so sánh `RecursiveChunker` vs `SlumberChunker` (Chonkie) trên `lichsu.md`. Dùng để tune chunking strategy trước khi build index thật.
```bash
python test.py --file lichsu.md --limit 6000 --skip-slumber
python test.py --file lichsu.md --slumber-model cx/gpt-5.4
```
Slumber dùng OpenAI-compatible endpoint qua `CHONKIE_SLUMBER_BASE_URL` (đang point tới một remote LLM gateway — xem `.env`).

### Tiền xử lý dataset (preprocessing)
Trước khi index, chạy pipeline tiền xử lý để chuẩn hóa heading, dash (–/—→-), smart quote (“”→”), ellipsis (…→...), gộp blank line. Ngoài ra `lichsu.md` còn có **soft hyphen U+00AD** xen giữa từ tiếng Việt (di chứng copy từ PDF/DOCX có hyphenation) — phải strip vì sẽ phá tokenization/embedding.

**Lưu ý quan trọng**: preprocessing **KHÔNG** tách paragraph dài. `lichsu.md` có vài section không có paragraph break (lớn nhất `## 7. Phong trào Cần vương` ~652K chars). Chunking pipeline xử lý trường hợp này qua Level 4 fallback (`_fallback_sentence_merge`).

```bash
# Trên Windows PowerShell, set encoding để in tiếng Việt
$env:PYTHONIOENCODING="utf-8"

# Dry-run (chỉ in report, không ghi file)
cd apps/agent-service
python scripts/preprocess_dataset.py --input ../../lichsu.md --limit 50000

# Ghi file đã chuẩn hóa
python scripts/preprocess_dataset.py --input ../../lichsu.md --output ../../lichsu.clean.md
```

Pipeline là **idempotent** và **non-destructive**: chạy nhiều lần ra cùng kết quả, không xóa/sửa câu chữ, chỉ chuẩn hóa whitespace + Unicode. Trả về `PreprocessReport` với counter cho từng loại fix (dùng cho logging/observability). Test: `pytest tests/test_preprocessing.py`.

Khi build full indexing pipeline, gọi `preprocess_text()` ngay sau load document, trước khi đưa vào Chonkie.

## Configuration

`.env` ở root được docker-compose load cho **tất cả services**. Mỗi app cũng có `.env.example` riêng cho local dev:
- `apps/agent-service/.env.example` — LLM keys, Qdrant/Neo4j/Redis URLs, `RAG_TOP_K`, `HYBRID_ENABLED`, `GRAPHRAG_ENABLED`
- `apps/backend/.env.example` — `BACKEND_SECRET_KEY`, `DATABASE_URL`, `AGENT_SERVICE_URL`, JWT settings
- `apps/frontend/.env.example` — chỉ vars có prefix `VITE_` mới expose ra browser

LLM default: `gpt-4o-mini` (configurable via `LLM_MODEL`). Embedding default: `text-embedding-3-small`. Khi làm tiếng Việt nên cân nhắc switch sang `bge-m3` hoặc `multilingual-e5-large` cho retrieval quality.

## Domain-specific notes (lịch sử Việt Nam)

Đây là phần đặc thù domain mà code generic không cover:

- **Alias resolution**: "Nguyễn Tất Thành / Nguyễn Ái Quốc / Hồ Chí Minh / Bác Hồ" là cùng 1 entity. Extraction prompt và KG merge logic phải xử lý alias rõ ràng — đây là một trong những điểm contribution của đồ án.
- **Temporal anchor inheritance**: Document lịch sử có cấu trúc "Năm 1859, ... [paragraph]. Đầu năm 1861, ... [paragraph]". Các câu giữa các anchor inherit time/location từ anchor đầu segment. Chunking phải tôn trọng segment boundary thay vì split cứng theo độ dài.
- **Confidence + provenance**: Mỗi event lưu cả time/location lẫn `confidence` và `inferred_from_context` flag. Marker trên map render khác nhau theo confidence (đậm = explicit, nhạt = inferred).
- **Honest behavior**: Khi không đủ data → trả lời "chưa đủ thông tin" thay vì hallucinate. Quan trọng vì fact sai trong lịch sử bị trừ điểm nặng.

## Reference assets

- `lichsu.md` — corpus chính (~3MB, ~2.36M chars, 6.878 dòng), không index lại từ đầu nhiều lần (tốn API cost); cân nhắc versioning KG khi thay đổi extraction prompt.
- `trackasia-map-test.html` — standalone POC cho map rendering, dùng làm reference khi build `features/map`.
- `README.md` — đặc tả chức năng đầy đủ (admin, teacher, RAG, GraphRAG, hybrid, map, timeline, MVP scope vs future). Là nguồn truth cho scope.
- `docs/brainstorming/` — session notes về kiến trúc và ý tưởng.
