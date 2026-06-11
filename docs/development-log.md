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

