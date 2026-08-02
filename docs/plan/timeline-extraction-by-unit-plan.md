# Plan: Extract timeline theo unit, trả kết quả theo chunk

**Trạng thái:** ✅ **Đã code xong toàn bộ §1–§10 (2026-08-02)**, lint/type/test sạch
(388 test pass). **Rollout §11 mới xong bước 1–2** (unit test + build lại units cap 30K:
366 unit, median 5.952 ký tự, max 29.969, overlap 0, phủ đủ 1683/1683 chunk) — **chưa
gọi LLM lần nào với `timeline-extract-v4`**, bảng `timeline_events` vẫn giữ dữ liệu cũ
(provenance cấp unit). Xem "Trạng thái triển khai" ở §13 cuối file.

Plan này thay thế phương án extract từng chunk kèm previous context; file kế hoạch cũ chỉ
được giữ lại làm lịch sử thử nghiệm.

## 1. Mục tiêu

Giữ cách gom nhiều chunk thành một unit để LLM có đủ ngữ cảnh suy luận năm, thời gian,
địa điểm và các tham chiếu nằm ở những chunk lân cận. Mỗi unit chỉ gọi LLM một lần, nhưng
kết quả cuối cùng được lưu riêng theo từng chunk để UI chỉ lấy timeline/location của những
chunk thực sự được sử dụng trong câu trả lời.

Luồng mới:

```text
chunks_llm.json
  -> build unit tối đa 30.000 ký tự, không overlap
  -> gửi toàn bộ chunk có marker trong một lần gọi LLM
  -> kiểm tra kết quả đủ cho mọi chunk trong unit
  -> lưu timeline_extractions.json theo chunk_id
  -> reconcile/dedup và gắn source_chunk_ids
  -> PostgreSQL timeline_events
  -> timeline/map trên UI
```

## 2. Build unit

Giữ thuật toán hiện tại: tách riêng từng `source_file`, giữ đúng thứ tự văn bản và ưu tiên
ranh giới heading. Thay đổi contract như sau:

- `CAP_CHARS = 30_000`.
- Không cắt đôi một raw chunk.
- Không overlap, không previous context và không context-only chunk.
- Mỗi raw chunk hợp lệ phải xuất hiện trong đúng một unit.
- Unit giữ nguyên từng chunk thay vì chỉ nối thành một trường `text` phẳng.
- `unit_id` tiếp tục lấy từ chunk đầu và chunk cuối để phục vụ log, resume và audit.
- Nếu một raw chunk đơn lẻ vượt 30.000 ký tự, cho chunk đó thành một unit riêng và cảnh báo;
  không cắt nội dung âm thầm.

Invariant bắt buộc:

```python
assert all(count == 1 for count in chunk_usage.values())
```

Định dạng `timeline_units.json`:

```json
{
  "cap": 30000,
  "source_file": "chunks_llm.json",
  "count": 1,
  "units": [
    {
      "unit_id": "phi-su-kien_clean-000001__phi-su-kien_clean-000003",
      "heading_path": ["PHẦN MỘT", "Chương I"],
      "chunks": [
        {
          "chunk_id": "phi-su-kien_clean-000001",
          "text": "..."
        },
        {
          "chunk_id": "phi-su-kien_clean-000002",
          "text": "..."
        },
        {
          "chunk_id": "phi-su-kien_clean-000003",
          "text": "..."
        }
      ]
    }
  ]
}
```

Không lưu `source_chunk_ids` riêng trong unit vì có thể lấy trực tiếp từ
`chunks[].chunk_id`.

## 3. Input gửi LLM

Mỗi unit được render thành một input có marker rõ ràng:

```xml
<heading_context>
PHẦN MỘT > Chương I
</heading_context>

<unit_context>
  <chunk ref="1">Năm 1862, nghĩa quân...</chunk>
  <chunk ref="2">Đêm 16 rạng 17 tháng 12...</chunk>
  <chunk ref="3">Sự kiện diễn ra tại...</chunk>
</unit_context>
```

LLM được phép dùng toàn bộ unit để:

- suy ra năm còn thiếu từ đoạn trước;
- giải tham chiếu như “sau đó”, “tại đây”, “lực lượng này”;
- hiểu một diễn biến trải qua nhiều chunk.

Tuy nhiên, event phải được trả dưới chunk chứa thông tin/diễn biến làm bằng chứng cho event.
Nếu cùng một event được mô tả ở nhiều chunk, event có thể xuất hiện ở nhiều chunk và sẽ được
reconcile ở bước sau.

**Rule bắt buộc — nhãn nhất quán khi một event lặp ở nhiều `chunk_ref`:** trước đây một unit
chỉ gọi LLM một lần và model tự nhất quán nội bộ; nay `reconcile.py` gộp event trùng bằng khoá
`(parent_norm, time_start, loc0_norm, label_norm)` (uuid5) nên NẾU model diễn đạt lệch nhau
giữa hai chunk_ref (vd "Quân Pháp tấn công Đà Nẵng" ở ref 2 vs "Pháp tấn công Đà Nẵng" ở ref 5)
sẽ ra hai `event_id` khác nhau thay vì gộp một. Prompt phải yêu cầu rõ: khi cùng một event xuất
hiện ở nhiều `chunk_ref` trong cùng response, dùng NGUYÊN VĂN cùng một `label` (và cùng
`time_start`/`locations[0]` nếu cùng mốc) cho mọi lần xuất hiện, để reconcile match đúng.

Trong thay đổi này chưa siết thêm rule location; ưu tiên đổi cấu trúc extraction trước.

## 4. Raw output từ LLM

Structured output bắt buộc trả một `chunk_results` cho mọi marker đầu vào, kể cả chunk không
có event:

```json
{
  "chunk_results": [
    {
      "chunk_ref": "1",
      "events": [
        {
          "label": "Quân Pháp tấn công Đà Nẵng",
          "summary": "Quân Pháp mở cuộc tấn công tại Đà Nẵng.",
          "time_start": "1858-09-01",
          "time_end": "",
          "locations": ["Đà Nẵng"],
          "parent_event": "",
          "confidence": "cao"
        }
      ]
    },
    {
      "chunk_ref": "2",
      "events": []
    }
  ]
}
```

Validation bắt buộc trước khi ghi cache:

- mỗi `chunk_ref` đầu vào xuất hiện đúng một lần;
- không thiếu ref, không trùng ref và không có ref lạ;
- mọi `events` đúng schema;
- `events: []` là kết quả hợp lệ.

Nếu validation thất bại, không ghi một phần kết quả của unit; đánh dấu lỗi để retry toàn bộ
unit.

## 5. Output/cache `timeline_extractions.json`

Sau validation, code ánh xạ marker về chunk ID thật và lưu phẳng theo chunk:

```json
{
  "phi-su-kien_clean-000001": {
    "prompt_version": "timeline-extract-v4",
    "unit_id": "phi-su-kien_clean-000001__phi-su-kien_clean-000003",
    "events": [
      {
        "label": "Quân Pháp tấn công Đà Nẵng",
        "summary": "Quân Pháp mở cuộc tấn công tại Đà Nẵng.",
        "time_start": "1858-09-01",
        "time_end": "",
        "locations": ["Đà Nẵng"],
        "parent_event": "",
        "confidence": "cao"
      }
    ]
  },
  "phi-su-kien_clean-000002": {
    "prompt_version": "timeline-extract-v4",
    "unit_id": "phi-su-kien_clean-000001__phi-su-kien_clean-000003",
    "events": []
  },
  "phi-su-kien_clean-000003": {
    "prompt_version": "timeline-extract-v4",
    "unit_id": "phi-su-kien_clean-000001__phi-su-kien_clean-000003",
    "events": []
  }
}
```

Không lưu các field sau trong cache:

- `source_chunk_ids`;
- `context_chunk_ids`;
- `context_hash` hoặc `input_hash`;
- `heading_path` nếu không cần cho màn hình debug.

Key ngoài cùng chính là source chunk. `unit_id` vẫn cần để xác định một unit đã hoàn thành
và truy ngược request đã sinh ra kết quả.

## 6. Resume

Giữ resume và dùng chính `timeline_extractions.json` làm checkpoint, không tạo thêm cache.

Một unit chỉ được coi là hoàn thành khi tất cả chunk trong unit đều có entry với:

- `prompt_version` khớp phiên bản hiện tại;
- `unit_id` khớp unit hiện tại.

Nếu thiếu một chunk hoặc metadata không khớp, gọi lại toàn bộ unit và ghi đè toàn bộ entry
của unit đó. Cache được ghi atomically sau mỗi số lượng unit cấu hình hoặc sau mỗi batch.

Vì không có context hash, khi text thay đổi nhưng chunk ID giữ nguyên phải:

- tăng `prompt_version`; hoặc
- chạy với `--overwrite`.

## 7. Reconcile và database

Reconcile đọc từng entry theo chunk:

```python
source_chunk_ids = [chunk_id_from_outer_key]
```

Nếu cùng một event xuất hiện ở nhiều chunk, dedup giữ một `event_id` và hợp nhất
`source_chunk_ids`. `event_id` vẫn dùng để định danh/dedup/liên kết timeline với marker;
`source_chunk_ids` trong database vẫn dùng để map các chunk được cite/retrieve sang event.

Không đổi schema bảng `timeline_events`, API visualization hoặc frontend trong migration này.
UI tiếp tục query event theo giao của `source_chunk_ids` với các chunk được dùng trong câu trả
lời, nhưng provenance lúc này chính xác ở cấp chunk thay vì cấp unit.

## 8. Một lần gọi LLM cho mỗi unit

Luồng mới chỉ gọi một lần cho mỗi unit. Completeness pass cũ dành cho unit trên 40.000 ký tự
không còn chạy vì cap mới là 30.000 và output cần được phân bổ theo chunk trong cùng response.

Không gọi lại riêng từng chunk sau khi đã nhận kết quả unit.

## 9. Các phần code cần sửa

1. `segmenter.py`: cap 30.000, bỏ overlap, đổi `Unit` để giữ `chunks`.
2. `run_segmentation.py`: serialize/report format unit mới và kiểm tra coverage đúng một lần.
3. Schema timeline extraction: thêm `chunk_results` và `chunk_ref`.
4. Prompt timeline: gửi marker, yêu cầu trả đủ kết quả cho từng ref, và yêu cầu dùng nguyên
   văn cùng một `label` (+ `time_start`/`locations[0]` nếu cùng mốc) khi cùng một event xuất
   hiện ở nhiều `chunk_ref` (để reconcile match đúng, xem §3).
5. `atomic_event_extractor.py`: một response cho toàn unit, bỏ completeness pass.
6. `run_timeline_index.py`: validate ref, flatten cache theo chunk và resume theo unit.
7. `reconcile.py`: lấy source chunk từ key ngoài cùng và union source khi dedup.
8. Cập nhật test và hướng dẫn CLI.

## 10. Test bắt buộc

- Cùng input và cap tạo cùng danh sách unit.
- Không unit nào trộn hai `source_file`.
- Mỗi raw chunk hợp lệ xuất hiện đúng một lần; overlap bằng 0.
- Unit không vượt 30.000 ký tự, trừ một raw chunk đơn lẻ đã vượt cap và có cảnh báo.
- Marker ánh xạ đúng về chunk ID thật.
- Missing, duplicate và unknown `chunk_ref` đều làm fail toàn unit.
- Chunk không có event vẫn được cache với `events: []`.
- Unit cache thiếu một chunk phải được resume lại toàn bộ.
- Cache đủ và đúng version/unit ID phải được skip.
- Reconcile gắn đúng source chunk và union source khi cùng event nằm ở nhiều chunk.
- Cùng `label`/`time_start`/`locations[0]` ở hai `chunk_ref` khác nhau (cùng unit) phải gộp
  đúng một `event_id` ở reconcile, không tạo hai event trùng.
- Query UI bằng một chunk không kéo theo toàn bộ event của unit.

## 11. Rollout

1. Sửa code và chạy unit test, chưa ghi database.
2. Build lại `timeline_units.json` với cap 30.000; kiểm tra coverage và overlap bằng 0.
3. Extract thử 1–2 unit thật, in nguyên raw output và cache sau khi flatten để review.
4. Chạy full extraction với `--skip-db`, resume qua cache.
5. Review thống kê time/location và một số unit ngẫu nhiên.
6. Reconcile với `--skip-db`, kiểm tra event và provenance.
7. Chỉ replace bảng `timeline_events` sau khi kết quả được duyệt.
8. Build lại gazetteer nếu tập location thay đổi.

Cache/unit artifact cũ không bị xóa trong lần migration đầu để có thể rollback.

## 12. Tiêu chí hoàn thành

- Cap production là 30.000 ký tự.
- Không có chunk overlap.
- Một unit tương ứng đúng một LLM request.
- Mọi chunk của unit có một entry trong `timeline_extractions.json`.
- Resume không gọi lại unit đã hoàn thành và gọi lại toàn bộ unit dở dang.
- Event trong database có provenance chính xác ở cấp chunk.
- UI chỉ hiển thị timeline/location liên quan đến những chunk thực sự được sử dụng.

## 13. Trạng thái triển khai (2026-08-02)

### Đã code + verify (không tốn LLM)

| § | Hạng mục | File | Ghi chú |
|---|---|---|---|
| 2 | Cap 30K, bỏ overlap, `Unit.chunks` | `app/indexing/timeline/segmenter.py` | Thêm `UnitChunk`; bỏ `Unit.text`/`source_chunk_ids`/`_SEP`/`_OVERLAP`. Chunk đơn lẻ > cap → unit riêng + `log.warning`. |
| 2 | Invariant "mỗi chunk 1 unit" | `scripts/run_segmentation.py` | `_check_invariant` → vỡ thì **không ghi artifact**, thoát mã 1 (verify: chunk_id trùng → chặn đúng). |
| 4 | `chunk_results` + `chunk_ref` | `app/schemas/timeline.py` | `ChunkEvents` mới; `TimelineExtraction.events` → `.chunk_results`. Verify strict json_schema hợp lệ (nested array-of-object 2 tầng, mọi field required). |
| 3 | Marker + rule nhãn nhất quán | `app/prompts/timeline_extract.py` | `v3` → **`v4`**. Thêm `<output_contract>` + `<attribution>`; `build_user_prompt` nhận `list[(ref, text)]`. 3 few-shot viết lại theo `<unit_context>`. |
| 4,8 | 1 request/unit + validate ref | `app/indexing/timeline/atomic_event_extractor.py` | `extract_timeline_events` → **`extract_unit_events`** (trả `{chunk_id: events}`). Xoá completeness pass + `_merge_dedup`/`_dedup_key`/`_parse_events`. Thêm `TimelineExtractionError`. |
| 5,6 | Cache theo chunk + resume theo unit | `scripts/run_timeline_index.py` | `_unit_done` (đủ chunk + khớp `prompt_version` **và** `unit_id`); `_load_artifact` **từ chối cache format cũ**; `_show_units` in theo ref. |
| 7 | Source chunk từ khoá ngoài | `app/indexing/timeline/reconcile.py` | `source_chunk_ids = [chunk_id]`, union khi dedup. |
| 10 | Test | `tests/test_{segmenter,timeline_extract,reconcile}.py` | 11 + 12 + 9 test; phủ đủ 11 mục §10. |

### Còn lại — cần user chạy (tốn API)

1. Build lại artifact thật: `python scripts/run_segmentation.py` (ghi đè
   `dataset/timeline_units.json` bản cap 50K cũ).
2. Đổi tên cache cũ để giữ rollback — bắt buộc, script sẽ chặn nếu không làm:
   `Rename-Item dataset/timeline_extractions.json timeline_extractions.unit-keyed.json`
3. Rollout §11 bước 3→8: trích thử 1–2 unit → review → full `--skip-db` → reconcile
   `--skip-db` → chỉ replace `timeline_events` sau khi duyệt.

### Cân nhắc đã ghi nhận nhưng CHƯA làm (có chủ đích)
- **Đo lại recall sau khi bỏ completeness pass**: chưa có số so sánh trước/sau trên section
  đã biết. Nên làm ở §11 bước 5 (so số event/chunk giữa cache v2 cũ và v4 mới trên cùng
  vài unit) trước khi replace bảng.
- **Prune cache**: entry `chunk_id` không còn thuộc unit nào (corpus đổi) sẽ nằm lại và vẫn
  vào reconcile. Không xử lý vì migration này trích lại từ cache trắng; chỉ thành vấn đề khi
  corpus thay đổi về sau.
- **Event vắt qua ranh giới 2 unit**: bỏ overlap nên không còn lưới vớt. Chấp nhận có chủ
  đích, đổi lấy provenance chính xác — và chỉ xảy ra ở section phải cắt cứng theo chunk
  (`_chunk_split`), vốn không kích hoạt trên corpus hiện tại (366/366 unit gom theo heading).
