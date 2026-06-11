# Kế Hoạch Triển Khai: LLM-Guided Sentence Indexing Chunking

Kế hoạch này thiết lập pipeline chia chunk nâng cao cho tài liệu lịch sử Việt Nam, sử dụng LLM để xác định các ranh giới cắt đoạn dựa trên ngữ nghĩa câu (Sentence Indexing) và dùng Python thực hiện cắt vật lý để bảo toàn chỉ số dòng và ký tự gốc.

## 1. Nguyên Tắc Thiết Kế & Xử Lý

*   **Giới hạn Output của LLM:** Mặc dù mô hình (`gpt-4o-mini` hoặc `gpt-5.4-mini`) hỗ trợ context đầu vào lớn (258k), giới hạn token đầu ra vẫn ở mức thấp hơn (thường 4096 tokens). Bằng cách chỉ bắt LLM trả về danh sách số nguyên chỉ mục câu cần cắt (ví dụ: `[12, 34, 45]`), chúng ta đảm bảo tốc độ cực nhanh, hóa đơn API tối thiểu và không bao giờ bị cắt cụt câu trả lời.
*   **Mức độ phụ thuộc mạng:** Phương án này đòi hỏi gọi API OpenAI khi lập chỉ mục (Indexing). Để tối ưu chi phí và tránh bị nghẽn (rate limits), chúng ta cần gửi các request theo cụm (Batching) hoặc chạy bất đồng bộ (Async).
*   **Cơ chế dự phòng (Fallback):** Nếu LLM bị lỗi kết nối hoặc trả về định dạng sai, hệ thống sẽ tự động chuyển sang sử dụng bộ chia chunk toán học `RecursiveChunker` của Chonkie để đảm bảo quá trình index không bị gián đoạn.
*   **Chiến lược Overlap (Trùng lặp):** Với việc chia chunk thông minh theo ngữ nghĩa, nếu cần tạo overlap, hệ thống sẽ tự động lấy dòng cuối cùng của chunk trước chèn lên đầu của chunk sau ở tầng Python.

---

## 2. Quy Trình Chia Chunk Cấu Trúc (Phân Cấp)

Bộ chia chunk (`llm_chunker.py`) hoạt động theo các bước phân cấp từ thô đến tinh:

1.  **Cấp độ 1 (Chia theo Heading - Pre-split):** 
    - Quét toàn bộ file `lichsu.clean.md`.
    - Nhóm văn bản theo các headings thấp nhất để tạo ra các `sections` trung gian độc lập.
2.  **Cấp độ 2-3 (Gom theo đoạn văn `\n\n` rồi dòng `\n` — dùng Chonkie):**
    - Mỗi `section` body được đưa vào **Chonkie `RecursiveChunker`**, cấu hình `RecursiveRules` **chỉ 2 bậc**: paragraph (`\n\n`) → line (`\n`), đo độ dài bằng tokenizer tiếng Việt (`count_tokens`), `chunk_size=700`, `min_characters_per_chunk` theo config.
    - Chonkie tự gom các đoạn/dòng liên tiếp sao cho mỗi chunk <= 700 tokens (thay cho thuật toán gom thủ công trước đây).
    - **Giới hạn Chonkie tới bậc `\n`** (không cho cắt nhỏ hơn xuống câu/từ): nhờ vậy nếu một khối vẫn > 700 tokens mà không còn `\n`, Chonkie trả về nguyên khối quá khổ → chuyển sang Cấp độ 4.
    - Lưu ý: chuỗi heading `h1→h6` KHÔNG do Chonkie cung cấp — vẫn lấy từ `heading_parser` (Cấp độ 1). Chonkie chỉ chạy trên body từng section.
4.  **Cấp độ 4 (Gọi LLM chia nhỏ khối văn bản quá dài):**
    - Gửi thẳng khối văn bản quá dài sang OpenAI API, kèm yêu cầu trả về danh sách **anchor snippet** — chuỗi 8-12 từ đầu tiên (sao chép nguyên văn) của mỗi đoạn MỚI cần tách (không tính đoạn đầu).
    - LLM trả JSON `{"anchors": ["<đầu đoạn 2>", "<đầu đoạn 3>", ...]}`. Lý do dùng anchor thay vì chỉ số ký tự: LLM đếm vị trí ký tự rất hay sai, còn anchor thì Python tự định vị chính xác.
5.  **Cắt vật lý bằng Python:**
    - Với mỗi anchor, dùng `str.find()` (tìm tuần tự từ vị trí trước) để lấy `char_offset` chính xác trong khối. Bỏ anchor không tìm thấy hoặc không tăng dần.
    - Thực hiện cắt chuỗi vật lý trên văn bản gốc để thu được các chunk thành phẩm, đảm bảo giữ nguyên vẹn 100% định dạng gốc (dấu xuống dòng, khoảng trắng) và tính toán chính xác chỉ số dòng (`start_line`, `end_line`) và vị trí ký tự (`start_index`, `end_index`) dùng cho Citation.
    - Nếu LLM lỗi hoặc không cho được điểm cắt hợp lệ → fallback Chonkie `RecursiveChunker(chunk_size=700)`.

---

## 3. Các File Mã Nguồn Dự Kiến Thêm Mới

### Thư mục: `apps/agent-service/app/indexing/`

*   **[llm_chunker.py](file:///d:/Đồ%20án%20tốt%20nghiệp/apps/agent-service/app/indexing/llm_chunker.py)**
    - Triển khai logic phân loại, gộp nhóm paragraph, phân tách thứ cấp bằng `\n` và gọi LLM lấy anchor snippet (điểm cắt) cho khối quá dài.
*   **[chunk_slicer.py](file:///d:/Đồ%20án%20tốt%20nghiệp/apps/agent-service/app/indexing/chunk_slicer.py)**
    - Cắt vật lý dựa trên `char_offset` (từ anchor), định dạng và đóng gói metadata hoàn chỉnh (như `headings`, `token_count`, `embedding_text`).

### Thư mục: `apps/agent-service/scripts/`

*   **[run_llm_chunking.py](file:///d:/Đồ%20án%20tốt%20nghiệp/apps/agent-service/scripts/run_llm_chunking.py)**
    - Script CLI chạy toàn bộ pipeline: đọc dữ liệu làm sạch -> chia chunk -> xuất kết quả ra file `dataset/chunks_llm.json`.
