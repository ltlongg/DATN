# Nhật Ký Phát Triển Dự Án - Agentic RAG Lịch Sử Việt Nam

Tài liệu này ghi lại chi tiết các mốc thời gian, công việc đã hoàn thành và kế hoạch phát triển dự án theo từng ngày để phục vụ theo dõi tiến độ và viết báo cáo đồ án tốt nghiệp.

---

## [09/06/2026] - Khởi động & Cấu hình Hạ tầng

**Thời gian hoạt động:** Buổi chiều

### Công việc đã làm:
1. **Cấu hình môi trường hạ tầng:**
   - Tạo và hoàn thiện file [.env](file:///d:/Đồ%20án%20tốt%20nghiệp/.env) và [.env.example](file:///d:/Đồ%20án%20tốt%20nghiệp/.env.example) ở thư mục gốc.
   - Thiết lập đầy đủ các biến môi trường kết nối cho các dịch vụ: PostgreSQL, Redis, Neo4j, Qdrant và OpenAI API (LLM & Embeddings).
2. **Cập nhật thiết kế lưu trữ (Storage Plan):**
   - Thống nhất mô hình lưu trữ đa cơ sở dữ liệu (Polyglot Persistence) trong tài liệu [chunking-embedding-plan.md](file:///d:/Đồ%20án%20tốt%20nghiệp/docs/plan/chunking-embedding-plan.md).
   - Thiết lập nhiệm vụ cụ thể:
     - **PostgreSQL**: Lưu trữ bản ghi thô đầy đủ của chunk và `JSONB` metadata (chân đế dữ liệu).
     - **Qdrant**: Chỉ lưu ID vector và một tập con metadata payload (`headings`, `times`, `locations`, `source_file`) phục vụ Pre-filtering.
     - **Neo4j**: Lưu cấu trúc thực thể (Entities/Relationships) kèm liên kết `source_chunk_ids` về Postgres.
3. **Phân tích dữ liệu lịch sử thô ([lichsu.md](file:///d:/Đồ%20án%20tốt%20nghiệp/lichsu.md)):**
   - Đọc và đánh giá chất lượng file dữ liệu.
   - Xác định 5 vấn đề cần tiền xử lý (Preprocessing):
     - Thiếu dấu cách sau dấu chấm/phẩy (ví dụ: `tan.Sau`, `bộ,xung`).
     - Định dạng tiêu đề không đồng đều (ví dụ: `## 1.Khởi nghĩa` vs `## 2. Khởi nghĩa`).
     - Dấu ngoặc kép thông minh dạng cong (`“` và `”`) cần đưa về dấu thẳng (`"`).
     - Loại bỏ các ký tự ẩn nguy hại như soft hyphen `U+00AD`.
     - Tách các đoạn văn (Paragraphs) quá dài trong file gốc để tránh làm gãy bộ chia chunk.

4. **Thiết lập Kế hoạch Chia Chunk Tối ưu ([llm-chunking-plan.md](file:///d:/Đồ%20án%20tốt%20nghiệp/docs/plan/llm-chunking-plan.md)):**
   - Đề xuất và thống nhất cơ chế chia chunk phân cấp thông minh:
     - Chia theo Heading thấp nhất tạo `sections`.
     - Phân tách đoạn văn bằng `\n\n` và gộp nhóm tự động bằng Python để tạo chunk tối ưu dưới 700 tokens (miễn phí).
     - Phân tách thứ cấp bằng `\n` cho các cấu trúc danh sách, thơ, bảng biểu nếu đoạn văn quá dài.
     - Chỉ sử dụng LLM (`Sentence Indexing`) để băm nhỏ các khối văn bản thô cực lớn vượt ngưỡng 700 tokens không thể tự cắt bằng `\n` hoặc `\n\n`.
     - Cắt chuỗi vật lý trên Python để đảm bảo tọa độ ký tự và định dạng nguyên bản phục vụ Citation.

### Kế hoạch tiếp theo:
- Triển khai bộ phân tách câu `sentence_splitter.py` và module `llm_chunker.py` theo đúng kế hoạch.
- Viết script CLI `run_llm_chunking.py` và chạy thử nghiệm chia chunk thực tế trên dữ liệu lịch sử.

---

## [10/06/2026] - Triển khai LLM-Guided Chunking Pipeline

**Thời gian hoạt động:** Cả ngày

### Công việc đã làm:
1. **Quyết định thiết kế (chốt với 3 lựa chọn):**
   - Phạm vi phase này: **chỉ chunking → `dataset/chunks_llm.json`** (metadata nền + `embedding_text`); chưa extract metadata nội dung, chưa embed/nạp DB.
   - Tokenizer đếm ngưỡng 700: HF `AITeamVN/Vietnamese_Embedding` (bọc qua `count_tokens()` để dễ swap).
   - Bỏ `sentence_splitter.py` ở Level 4; LLM trả về **anchor snippet** (8-12 từ đầu mỗi đoạn mới), Python dùng `str.find()` định vị điểm cắt — đáng tin hơn char_offset thô.

2. **Code các module mới (`apps/agent-service/`):**
   - `app/core/config.py` (Settings/pydantic-settings) + `app/core/llm.py` (OpenAI client) — dựng nền `core/` vốn còn trống.
   - `app/indexing/token_counter.py` — lazy-load tokenizer VN, hàm `count_tokens()`.
   - `app/indexing/heading_parser.py` — Level 1, tách document thành `Section` theo heading stack, giữ offset tuyệt đối.
   - `app/indexing/chunk_slicer.py` — cắt vật lý, tính `start_line/end_line` + `start_index/end_index`, sinh `embedding_text` + token count.
   - `app/indexing/llm_chunker.py` — orchestrator Level 2-4 (greedy-pack paragraph/line → LLM anchor → fallback Chonkie), gộp chunk tí hon.
   - `app/prompts/chunk_split.py` (prompt Level 4, có version tag), `app/schemas/chunk.py` (Pydantic validate), `scripts/run_llm_chunking.py` (CLI).

3. **Nguyên tắc citation:** mọi offset tính trên `lichsu.clean.md` (file canonical sau preprocess), không phải `lichsu.md` gốc.

4. **Verify end-to-end (dữ liệu thật):**
   - Preprocess: `lichsu.md` (2.359.448 ký tự) → `lichsu.clean.md` (tách 354 paragraph dài).
   - Chunking full `--no-llm`: **196 sections → 2.131 chunks**, token avg ~294 (min 20, max 705), 0 lỗi schema.
   - Kiểm tra độc lập: 0/2131 lỗi offset, `chunk_index` liên tục, `chunk_id` duy nhất, không chunk rỗng, `embedding_text` đúng format.
   - Test: 30/30 pass (gồm 23 test mới cho heading_parser/chunk_slicer/llm_chunker dùng mock LLM + stub tokenizer).

5. **Sửa lỗi định dạng tiêu đề (Bug Fix):**
   - **Vấn đề:** Các tiêu đề như "Xung đột biên giới Việt Nam - Campuchia", "Xung đột Thái Lan - Việt Nam" và "Chiến tranh biên giới Việt - Trung 1979" chỉ được cách dòng đơn (`\n`) trong `lichsu.md`. Khi chạy bộ tiền xử lý `cleaner.py`, chúng bị gom chung vào paragraph và dính vào cuối dòng trước đó (ví dụ: `... hoặc phải đi lưu vong. ## 7. Xung đột biên giới...`), làm cho `heading_parser.py` bỏ sót tiêu đề.
   - **Giải pháp:** Cập nhật `cleaner.py` thêm hàm `_normalize_heading_newlines` để cô lập mọi tiêu đề bắt đầu bằng `#` bằng đúng một dòng trống (`\n\n`) trước và sau.
   - **Kết quả:** 
     - 31/31 test cases đã **pass 100%**.
     - Chạy lại preprocess và chunking thành công: Nhận diện đúng **402 sections** (thay vì 196) và xuất ra **2.192 chunks** (thay vì 2.131 chunks) lưu tại [chunks_llm.json](file:///d:/Đồ%20án%20tốt%20nghiệp/dataset/chunks_llm.json).

### Kế hoạch tiếp theo:
- Chạy thử Level 4 LLM thật (có `OPENAI_API_KEY`) trên vài section đặc để kiểm tra chất lượng anchor.
- Extract metadata nội dung: `times` (regex), `actors/locations/events` (LLM/NER).
- Embedding + nạp Postgres/Qdrant, sau đó GraphRAG (Neo4j).

---

## [11/06/2026] - Pipeline Trích Xuất Metadata Nội Dung (LLM)

**Thời gian hoạt động:** Cả ngày

### Công việc đã làm:
1. **Trích metadata nội dung từng chunk bằng LLM Structured Outputs:**
   - Thêm prompt + schema Pydantic + extractor để lấy 4 trường `times`, `actors`, `locations`, `events` (surface form) từ nội dung mỗi chunk — phục vụ Qdrant payload (pre-filter) và visualization sau này.
   - Đây là pass metadata **tách biệt** với pass graph (entity-có-kiểu) làm sau — hai mục đích khác nhau, không gộp.
2. **CLI `scripts/run_metadata_extraction.py`:**
   - Đọc `dataset/chunks_llm.json`, hỗ trợ chạy **song song**, **resume** (bỏ qua chunk đã làm) và **overwrite**, ghi kết quả ra `dataset/chunks_meta.json`.
3. **Ổn định cấu hình monorepo:**
   - Sửa `agent-service` đọc `.env` từ **root repo** (đường dẫn tuyệt đối, không phụ thuộc CWD).
   - Xử lý `OPENAI_BASE_URL` rỗng → `None` (tránh `APIConnectionError`).
   - Chuẩn hóa lại `.env.example`: root `.env` là nguồn cấu hình chính.

### Kế hoạch tiếp theo:
- Dựng pipeline embedding + nạp dữ liệu vào Postgres/Qdrant.
- Thiết kế tầng GraphRAG (entity + quan hệ → Neo4j).

---

## [13/06/2026] - Chuyển Sang Pipeline GraphRAG Tự Triển Khai (DIY)

**Thời gian hoạt động:** Cả ngày

### Công việc đã làm:
1. **Gỡ bỏ hoàn toàn LightRAG (`lightrag-hku`):**
   - Lý do: impedance mismatch lặp lại — `ainsert_custom_chunks` không dựng graph, KV một-backend, bảng riêng không tái dùng data Postgres, luồng chuẩn không tải nổi metadata per-chunk.
   - Quyết định: tự ráp pipeline DIY bằng client trực tiếp. Ghi rõ lý do + thiết kế trong `docs/plan/chunking-embedding-plan.md`.
2. **Dựng pipeline offline `scripts/run_graph_index.py`:**
   - Luồng: đọc `chunks_llm.json` → upsert Postgres `rag_chunks` (source of truth) → embed + upsert Qdrant `history_vn_chunks` → trích entity/quan hệ (song song) → cache `dataset/graph_extractions.json` → merge Neo4j.
   - Flags: `--limit --workers --overwrite --remerge --skip-vectors --skip-graph`.
3. **Chốt các quyết định kiến trúc (không đề xuất lại LightRAG):**
   - **`chunk_id` là khóa nối DUY NHẤT**: Postgres PK ↔ Qdrant payload ↔ Neo4j `source_chunk_ids`.
   - **Qdrant**: point id = `uuid5(NS, chunk_id)` (deterministic, idempotent); payload đúng 6 field `CHUNK_VECTOR_META_FIELDS`, không lưu text.
   - **Neo4j**: label `:Entity` (key `name` canonical, UNIQUE constraint) + rel type `:REL` (prop `keyword`); MERGE idempotent, tích lũy `source_chunk_ids` + `descriptions` xuyên chunk.
   - **Embedding**: model tiếng Việt `AITeamVN/Vietnamese_Embedding` (nền BGE-M3, 1024-dim, cosine).

### Kế hoạch tiếp theo:
- Tinh chỉnh prompt trích entity/quan hệ để tăng chất lượng (giảm entity rác, gộp alias).
- Xác định scope MVP cho frontend.

---

## [15-16/06/2026] - Tinh Chỉnh Prompt Trích Graph & Scope Frontend

**Thời gian hoạt động:** Hai ngày

### Công việc đã làm:
1. **Tune prompt trích entity + quan hệ (`graph-extract-v6`):**
   - Cố định **7 loại entity**: Nhân vật, Tổ chức, Địa điểm, Sự kiện, Văn kiện, Chủ trương, Chức danh.
   - Yêu cầu canonicalize alias ngay khi trích (vd "Nguyễn Ái Quốc"/"Bác Hồ" → "Hồ Chí Minh") — đây là điểm contribution của đồ án.
   - Mục tiêu: tránh **bỏ sót** entity/quan hệ quan trọng, đồng thời tránh trích ra entity/quan hệ **rác**.
   - Dùng OpenAI Structured Outputs (strict json_schema), nạp few-shot theo domain từ `prompts/entity_type/history_vn.yml`.
2. **Cải thiện cache handling** trong `run_graph_index.py`: resume theo `prompt_version`, chỉ trích lại khi version đổi.
3. **Bổ sung scope frontend MVP** (`docs/design/frontend-scope.md`).

### Kế hoạch tiếp theo:
- Chạy trích graph trên toàn bộ chunk, cache ra artifact.
- Nạp đầy đủ cả 3 cơ sở dữ liệu.

---

## [17/06/2026] - Trích Graph Toàn Bộ & Hoàn Tất Nạp 3 Cơ Sở Dữ Liệu

**Thời gian hoạt động:** Cả ngày

### Công việc đã làm:
1. **Trích graph toàn bộ corpus → `dataset/graph_extractions.json`:**
   - Hoàn tất trích **1.213 chunk** (prompt `graph-extract-v6`, 0 lỗi).
   - Kết quả thô: **15.862 entity**, **15.057 quan hệ** (cache để inspect + resume, không trích lại tốn API).
2. **Embedding trên GPU (Google Colab) → notebook `dataset/colab_embed_upsert.ipynb`:**
   - Vì máy local chỉ có torch CPU (embed 1213 chunk tốn ~15-30 phút), chuyển sang embed trên GPU Colab (L4/A100) rồi upsert thẳng vào Qdrant remote.
   - Notebook tách cell theo bước, **resumable** qua `embed_progress.json`, helper (`point_id_for`, `make_payload`) sao y `app/core/qdrant.py` để point id + payload khớp tuyệt đối với pipeline local.
   - Bổ sung phần **merge Neo4j** vào cuối notebook (Cypher sao y `graph_store.py`) để Colab có thể nạp luôn graph (không gọi LLM).
3. **Nạp đầy đủ cả 3 cơ sở dữ liệu (verify thực tế):**
   - **Postgres `rag_chunks`**: 1.213 rows (text + metadata, source of truth).
   - **Qdrant `history_vn_chunks`**: 1.213 points, dim 1024, cosine.
   - **Neo4j**: **6.216 entity** nodes (dedup theo `name` từ 15.862 thô, ~61%) + **14.157 quan hệ** (mất ~6% do MATCH không thấy endpoint — đúng thiết kế, không tạo node rỗng).
4. **Quyết định framework cho orchestrator: LangGraph** (không dùng Deep Agents):
   - Bài toán là RAG server với luồng có cấu trúc (route intent → RAG/GraphRAG/hybrid → synthesize), cần control flow tùy biến (branching, parallel fan-out, reflection loop "đủ data chưa"), không cần planning/memory/file-management của Deep Agents.

### Kế hoạch tiếp theo:
- Kiểm tra chất lượng alias resolution trên Neo4j (vd các node trùng ngữ nghĩa của "Hồ Chí Minh").
- Bắt đầu phase retrieval: dựng `AgentState` + `StateGraph` trong `orchestrator/`, rồi lần lượt `tools/traditional_rag/`, `tools/graph_rag/`, `tools/hybrid/`.

---

## [19/06/2026] - Hệ Thống Alias Resolution Đa Tầng & Re-index Neo4j

**Thời gian hoạt động:** Cả ngày

### Công việc đã làm:
1. **Chuẩn hóa `norm_name` về KIỂU CŨ (vị trí dấu thanh) — `app/indexing/graph/normalize.py`:**
   - Trước đây dời dấu thanh cụm oa/oe/uy về nguyên âm sau (kiểu mới) → sinh chữ sai như `mùa→muà`, `của→cuả` (cụm "ua" có dấu vốn nằm đúng trên 'u').
   - Đảo chiều về **kiểu cũ** (dấu trên nguyên âm đầu): `hoà→hòa`, `thuý→thúy`, giữ nguyên `mùa`/`của`.
   - Hai chốt chặn bắt buộc: chỉ dời khi cụm **cuối âm tiết** (loại âm tiết đóng `toàn`/`hoàng` và tam trùng âm `ngoài`/`xoáy`); bỏ qua digraph `qu` (`quả`/`quý`).
2. **Tầng alias 2b — dựng + duyệt `dataset/alias_seed.json`:**
   - Hiểu rõ pipeline 2 nguồn: verdict LLM `same`+`cao` → tự gom vào `alias_map.json`; `same`+`vừa` → ra `alias_review.md` cho người duyệt; alias ngữ nghĩa (Hồ Chí Minh / Nguyễn Ái Quốc) → khai tay vào `alias_seed.json`.
   - Duyệt 53 cặp "vừa": phân loại an toàn / cần cẩn thận / rủi ro cao. Với nhóm rủi ro **đối chiếu mô tả thật trong `graph_extractions.json`** thay vì đoán theo trí nhớ.
   - Phát hiện & loại 1 cặp sai: `"Chính phủ liên hiệp"` thực chất là **CP Liên hiệp VN 1946** (4/5 mô tả), không phải Lào. Sửa chiều canonical sai: `Trại Hút → Trái Hút`.
   - Chốt `alias_seed.json` (~29 cụm), build lại `alias_map.json` → **169 biến thể** (build từ verdict cache, **0 gọi LLM**).
3. **Sửa bug có sẵn — `app/indexing/graph/alias.py`:**
   - `_REPO_ROOT = parents[4]` trỏ sai `D:\VFS\apps\dataset\` (không tồn tại) → `load_alias_map()` **luôn trả rỗng** → `resolve()` chưa bao giờ chạy, tầng alias 2b vô hiệu từ trước tới nay. Sửa thành `parents[5]`.
   - Migrate khóa `alias_map.json` (11) + `alias_verdicts.json` (144) cho khớp normalize mới, 0 va chạm.
4. **Wipe + re-index Neo4j với schema mới:**
   - Phát hiện 6.216 node cũ là **schema đời trước**: không có `norm_name`, MERGE theo `name`, chưa qua alias → mọi việc trên chưa hề áp vào graph.
   - Xoá sạch Neo4j (node/quan hệ + constraint/index cũ), giữ nguyên Postgres + Qdrant (không phụ thuộc alias).
   - Re-merge từ cache (`run_graph_index.py --skip-vectors --remerge`, không tốn LLM): **5.857 entity** (giảm ~359 nhờ gom alias) + **14.088 quan hệ**, 100% node có `norm_name`.
   - Verify: "Hồ Chí Minh" gom về 1 node (95 chunks), "Quân đội Việt Nam" (27), "Lữ đoàn dù 173" gom 3 biến thể; các tên alias cũ không còn node riêng.

### Kế hoạch tiếp theo:
- Viết GraphRAG retriever (query side hiện chưa có) — **bắt buộc áp `resolve()` lên entity trong câu hỏi** trước khi MATCH `norm_name` (đối xứng với index), để hỏi bằng alias vẫn tìm đúng node.
- (Tùy chọn) lưu thêm field `aliases` trên node để trả lời minh bạch "còn gọi là...".
- Tiếp tục phase retrieval: `AgentState` + `StateGraph` trong `orchestrator/`.

