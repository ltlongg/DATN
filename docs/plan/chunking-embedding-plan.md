# Cấu Trúc Chunk, Metadata Và Retrieval Contract

## Mục Tiêu

Định nghĩa schema của một chunk, ý nghĩa từng trường metadata, cách `embedding_text` được xây dựng, và contract sử dụng metadata cho từng chế độ retrieval:

- `semantic_only`: chỉ dùng semantic RAG, có metadata để rerank/filter.
- `semantic_graph`: kết hợp semantic RAG với GraphRAG, metadata chỉ dùng nhẹ cho phạm vi lớn, citation và debug.

Nguyên tắc chính: metadata được lưu đầy đủ khi chunking, nhưng không phải mode nào cũng dùng hết metadata.

> Cách chia chunk thực tế (thuật toán, công nghệ, threshold) xem ở `llm-chunking-plan.md`.

## Quyết Định Chốt

- Embedding tạo từ `embedding_text`, gồm context từ `document_title`, `headings` và nội dung chunk.
- Nguồn chunking chính là `lichsu.md`; không dùng cây thư mục `dataset/` làm đơn vị chunk chính.
- Mỗi chunk lưu metadata nền lấy từ cấu trúc heading trong `lichsu.md`.
- Mỗi chunk có thể lưu metadata nội dung: `events`, `actors`, `times`, `locations`.
- Khi GraphRAG tắt, dùng metadata nội dung để hỗ trợ semantic RAG.
- Khi GraphRAG bật, để GraphRAG xử lý entity/relation; metadata nội dung không dùng làm filter cứng.
- Không dùng `locator` cho địa điểm lịch sử; dùng `locations`.
- Metadata cấu trúc dùng `document_title` và `headings` để tránh trùng dữ liệu kiểu `period/topic/path_hierarchy`.
- Vị trí trong file dùng `chunk_index`, `start_line`, `end_line`, `start_index`, `end_index`.

## Schema Metadata

Mỗi chunk có dạng:

```json
{
  "chunk_id": "lichsu-000007",
  "text": "...",
  "embedding_text": "...",
  "metadata": {
    "document_title": "lichsu.md",
    "headings": {
      "h1": "Nhật thuộc",
      "h2": "Trận Lạng Sơn(1940)"
    },
    "events": [
      "Phan Bội Châu bị bắt và quản thúc tại Huế",
      "Việt Nam Phục quốc Đồng minh Hội hoạt động trở lại"
    ],
    "actors": [
      "Việt Nam Phục quốc Đồng minh Hội",
      "Phục quốc Hội",
      "Phan Bội Châu",
      "Matsui Iwane",
      "Hoàng thân Cường Để"
    ],
    "times": ["1925-05", "1936", "1938"],
    "locations": ["Đông Dương", "Huế", "Nhật Bản", "Trung Quốc", "Nam Kỳ"],
    "source_file": "lichsu.md",
    "chunk_index": 7,
    "start_line": 496,
    "end_line": 504,
    "start_index": 12345,
    "end_index": 13500
  }
}
```

## Ý Nghĩa Các Trường

`document_title`: tên tài liệu nguồn chính. Với phase này là `lichsu.md`.

`headings`: cấu trúc ngữ cảnh của chunk theo cấp `h1`, `h2`, `h3`... Trường này được lấy trực tiếp từ heading trong `lichsu.md`.

Ví dụ file ít tầng:

```json
{
  "h1": "Nhật thuộc",
  "h2": "Trận Lạng Sơn(1940)"
}
```

Ví dụ section nhiều tầng:

```json
{
  "h1": "Thời kì cộng hòa",
  "h2": "Kháng chiến chống Mỹ (1955 - 1975)",
  "h3": "Mỹ can dự vào Chiến tranh Đông Dương"
}
```

Ví dụ section sâu:

```json
{
  "h1": "Thời kỳ cộng hoà",
  "h2": "Chiến tranh Đông Dương",
  "h3": "Quay lại giai đoạn 1950 -1954",
  "h4": "Chiến dịch Điện Biên Phủ",
  "h5": "Đợt 1",
  "h6": "Trận Him Lam"
}
```

`events`: các sự kiện cụ thể được nhắc trong chunk. Trường này có thể dài và không đồng nhất, nên không dùng filter cứng nếu không chuẩn hóa.

`actors`: nhân vật, tổ chức, lực lượng, quốc gia hoặc cơ quan được nhắc trong chunk.

`times`: mốc thời gian trong chunk. Có thể là `1940`, `1925-05`, hoặc ngày đầy đủ như `1945-08-19`.

`locations`: địa điểm lịch sử/địa lý được nhắc trong chunk.

`source_file`: đường dẫn file gốc, dùng cho citation và truy vết.

`chunk_index`: số thứ tự chunk trong file. Dùng để sắp xếp lại thứ tự, lấy chunk trước/sau và debug retrieval.

`start_line`, `end_line`: vị trí dòng của chunk trong `lichsu.md`. Dùng để citation/debug dễ đọc hơn vị trí ký tự.

`start_index`, `end_index`: vị trí ký tự của chunk trong file gốc. Dùng để highlight nguồn, debug chunking và tái tạo lại đoạn text từ file gốc.

## Metadata Nền

Metadata nền luôn được tạo bằng code/rule, không cần LLM:

```json
{
  "document_title": "lichsu.md",
  "headings": {
    "h1": "Nhật thuộc",
    "h2": "Trận Lạng Sơn(1940)"
  },
  "source_file": "lichsu.md",
  "chunk_index": 7,
  "start_line": 496,
  "end_line": 504,
  "start_index": 12345,
  "end_index": 13500
}
```

Cách suy ra:

```text
# Nhật thuộc
## 1.Trận Lạng Sơn(1940)
...

=> headings.h1 = "Nhật thuộc"
=> headings.h2 = "Trận Lạng Sơn(1940)"
```

## Metadata Nội Dung

Metadata nội dung có thể lấy bằng regex, danh sách entity, NER hoặc LLM:

```json
{
  "events": [],
  "actors": [],
  "times": [],
  "locations": []
}
```

Thứ tự ưu tiên:

1. `times`: lấy bằng regex trước vì rẻ và ít sai.
2. `actors`, `locations`: lấy bằng entity extractor hoặc LLM.
3. `events`: chỉ extract nếu cần, vì event phrase dễ bị không đồng nhất.

Không bắt buộc mọi chunk đều có đủ các field này. Nếu không chắc, để mảng rỗng.

## Embedding Text

`text` là nội dung gốc của chunk.

`embedding_text` là nội dung đưa vào model embedding. Format đề xuất:

```text
Tiêu đề tài liệu: lichsu.md
H1: Nhật thuộc
H2: Trận Lạng Sơn(1940)

{chunk_text}
```

Với section nhiều tầng:

```text
Tiêu đề tài liệu: lichsu.md
H1: Thời kỳ cộng hoà
H2: Chiến tranh Đông Dương
H3: Quay lại giai đoạn 1950 -1954
H4: Chiến dịch Điện Biên Phủ
H5: Đợt 1
H6: Trận Him Lam

{chunk_text}
```

Không nhồi toàn bộ `actors/events/locations` vào `embedding_text` mặc định, vì có thể làm nhiễu semantic search. Chỉ thêm khi benchmark chứng minh tốt hơn.

## Retrieval Mode: Semantic Only

Khi `use_graphrag = false`, hệ thống chỉ dùng semantic RAG. Metadata nội dung được dùng để hỗ trợ retrieval.

Luồng:

```text
User question
-> extract query hints: actors, events, times, locations
-> tạo embedding cho question
-> vector search lấy top N chunks
-> metadata rerank/boost
-> chọn top K chunks
-> LLM trả lời từ chunks
```

Ví dụ:

```text
Question: "Phan Bội Châu bị quản thúc ở đâu năm 1925?"
Hints:
  actors = ["Phan Bội Châu"]
  times = ["1925"]
```

Rerank:

```text
+ điểm nếu chunk có actors chứa "Phan Bội Châu"
+ điểm nếu chunk có times chứa "1925"
+ điểm nếu chunk có locations khi intent hỏi "ở đâu"
```

Ở mode này, metadata `actors/events/times/locations` rất hữu ích vì nó bù cho việc không có graph.

## Retrieval Mode: Semantic Graph

Khi `use_graphrag = true`, hệ thống kết hợp semantic RAG với GraphRAG.

Luồng:

```text
User question
-> semantic search lấy chunks gần nghĩa
-> GraphRAG tìm entities/relationships liên quan
-> gộp semantic chunks + graph context
-> LLM trả lời
```

Ở mode này:

- GraphRAG xử lý entity và relationship chính.
- Không dùng `actors/events/locations` làm filter cứng.
- Metadata vẫn dùng cho citation, debug, route phạm vi lớn và có thể filter nhẹ theo `document_title/headings/times`.

Ví dụ:

```text
Question: "Phan Bội Châu liên quan gì đến Phục quốc Hội?"
Semantic RAG: lấy đoạn văn gần nghĩa.
GraphRAG: lấy node/edge về Phan Bội Châu, Phục quốc Hội, Cường Để, Matsui Iwane.
Metadata: dùng source_file/chunk_index để dẫn nguồn.
```

## Luật Dùng Metadata Theo Mode

```python
def retrieve(question: str, use_graphrag: bool):
    hints = extract_query_hints(question)

    if not use_graphrag:
        candidates = vector_search(question, top_k=30)
        candidates = metadata_rerank(
            candidates,
            actors=hints.actors,
            events=hints.events,
            times=hints.times,
            locations=hints.locations,
        )
        return candidates[:5]

    semantic_chunks = vector_search(
        question,
        top_k=8,
        filter=build_light_filter(hints),
    )
    graph_context = graphrag_search(question)
    return merge_context(semantic_chunks, graph_context)
```

`build_light_filter` chỉ nên dùng field chắc chắn:

```json
{
  "document_title": "...",
  "headings.h1": "...",
  "headings.h2": "...",
  "times": "..."
}
```

Không dùng filter cứng theo `actors/events/locations` khi GraphRAG bật, trừ khi đã có chuẩn hóa alias tốt.

## Alias Và Chuẩn Hóa

Rủi ro lớn nhất của metadata nội dung là nhiều tên gọi cho cùng một thực thể:

```text
Việt Nam Phục quốc Đồng minh Hội
Phục quốc Hội
Việt Nam Độc lập Vận động Đồng minh Hội
```

Bản đầu có thể lưu tên gốc trong metadata. Nếu cần filter chính xác hơn, thêm field canonical:

```json
{
  "actors_canonical": [
    "viet_nam_phuc_quoc_dong_minh_hoi",
    "phan_boi_chau",
    "matsui_iwane",
    "cuong_de"
  ]
}
```

Không bắt buộc làm canonical ngay trong bản đầu.

## Lưu Trữ (Polyglot Persistence Plan)

Hệ thống sử dụng mô hình lưu trữ phân tán để tối ưu RAM và hiệu năng truy vấn:

### 1. PostgreSQL (Single Source of Truth)
Postgres lưu trữ toàn bộ dữ liệu thô, chi tiết định vị và full metadata của các chunks để phục vụ hiển thị Citation và quản trị.

```sql
CREATE TABLE rag_chunks (
    chunk_id TEXT PRIMARY KEY,               -- Ví dụ: 'lichsu_clean-000001'
    doc_id TEXT NOT NULL,
    lightrag_chunk_key TEXT NOT NULL UNIQUE, -- Khóa source_id của LightRAG
    text TEXT NOT NULL,                      -- Văn bản thô của chunk
    embedding_text TEXT NOT NULL,            -- Văn bản dùng để embed (kèm context headings)
    metadata JSONB NOT NULL,                 -- Full metadata gốc
    heading_path TEXT[] NOT NULL DEFAULT '{}',
    events TEXT[] NOT NULL DEFAULT '{}',
    actors TEXT[] NOT NULL DEFAULT '{}',
    times TEXT[] NOT NULL DEFAULT '{}',
    locations TEXT[] NOT NULL DEFAULT '{}',
    source_file TEXT NOT NULL,               -- File nguồn (lichsu.md)
    chunk_index INT NOT NULL,                -- Thứ tự chunk
    start_line INT,                          -- Dòng bắt đầu
    end_line INT,                            -- Dòng kết thúc
    start_index INT,                         -- Vị trí ký tự bắt đầu
    end_index INT,                           -- Vị trí ký tự kết thúc
    text_token_count INT,
    embedding_token_count INT
);
```

### 2. Qdrant (Vector Database - Chỉ lưu Vector & Filter Payload)
Qdrant chỉ lưu trữ ID, Vector Embedding và một **tập con metadata tối giản** cần thiết để thực hiện **Pre-filtering** (lọc trước khi so sánh vector). Tránh lưu text thô cồng kềnh trong Qdrant để tiết kiệm bộ nhớ RAM.

*   **ID:** Khớp hoàn toàn với `chunk_id` trong Postgres.
*   **Vector:** Sinh ra từ `embedding_text`.
*   **Payload (Metadata tối giản):**
    ```json
    {
      "chunk_id": "lichsu_clean-000001",
      "heading_path": ["Thời kì thuộc địa", "Khởi nghĩa Trương Định", "Diễn biến"],
      "events": ["Quân Pháp đánh chiếm thành Gia Định"],
      "actors": ["quân Pháp", "Trương Định"],
      "times": ["1859"],
      "locations": ["Gia Định"]
    }
    ```

### 3. Neo4j (Knowledge Graph - Lưu cấu trúc & Mối quan hệ)
Neo4j không lưu text thô dài của các chunks mà chỉ lưu các **Thực thể (Entities)** và **Mối quan hệ (Relationships)** được trích xuất.
*   **Đầu vào:** Đọc từ file/chunk → Extract qua LLM → Nạp vào Graph.
*   **Truy vết (Citation):** Mỗi Node hoặc Edge trong Neo4j lưu thuộc tính `source_chunk_ids` (mảng các `chunk_id` tương ứng trong Postgres) để hệ thống có thể truy vấn ngược lại Postgres khi cần dẫn nguồn.

## Field Suy Diễn Không Lưu

Không lưu riêng `period`, `topic`, `path_hierarchy` để tránh trùng dữ liệu.

Nếu cần trong code, suy diễn từ `headings`:

```python
period = metadata["headings"].get("h1")

def deepest_heading(headings: dict[str, str]) -> str | None:
    ordered = sorted(
        headings.items(),
        key=lambda item: int(item[0][1:])
    )
    return ordered[-1][1] if ordered else None

topic = deepest_heading(metadata["headings"]) or metadata["document_title"]
```

## Checklist

- Chunk không rỗng và không chỉ chứa heading.
- `document_title`, `headings`, `source_file`, `chunk_index` luôn có.
- `actors`, `locations`, `events` có thể rỗng nếu extractor không chắc.
- `embedding_text` có context heading đủ nhưng không quá nhiễu.
- `semantic_only` dùng metadata để rerank.
- `semantic_graph` không filter cứng bằng `actors/events/locations`.
- Citation trả được `source_file` và `chunk_index`.
- Có log/debug để xem vì sao chunk được chọn.

## Chưa Làm Trong Phase Đầu

- Chuẩn hóa alias/canonical entity toàn hệ thống.
- Metadata filter phức tạp trong retrieval core.
- LLM router tự chọn retrieval mode.
- Benchmark nhiều cấu hình `embedding_text` (có/không có actors/events).
