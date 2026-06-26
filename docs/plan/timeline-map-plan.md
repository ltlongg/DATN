# Plan: Lớp dữ liệu Timeline + Map cho câu trả lời

> Trạng thái: **Phase 1 → 7 đã build & verify**. Toàn pipeline offline + builder online
> xong: text → units → atomic events (`timeline_events`, 34) → geocode (`gazetteer`, 31,
> Google+LLM) → `build_visualization()` ra payload map+timeline link bằng event_id.
> **Chốt §5: Hướng A (segmenter), cap 50K. Chốt §9: geocoding Google→LLM** (đổi từ Mapbox
> sang Google 2026-06-22, xem §9). Còn lại: chạy full corpus + tích hợp builder vào answer
> flow agent (Phase 8). File này là source-of-truth của hạng mục timeline/map. Cập nhật
> khi đổi quyết định.
>
> **⚠️ Ưu tiên 2026-06-22 (user): TẠM HOÃN khâu toạ độ** (`gazetteer` + lat/lon) — để LÀM
> CUỐI, vì độ chính xác địa điểm quan trọng và cần review kĩ (điểm yếu trùng-tên §9). **Tạm
> thời KHÔNG chạy geocoding** (cả LLM-sinh lẫn Google Maps). Trọng tâm hiện tại: chỉ trích
> **time + location** (chuỗi tên địa danh, như `timeline_events` đang có). Geocoding là
> pipeline B độc lập (`scripts/build_gazetteer.py`) — KHÔNG chạy script đó là đủ, không cần
> sửa code; pipeline A (`run_timeline_index.py`) không import/phụ thuộc nó. Builder online
> gặp `gazetteer` rỗng → honest fallback: chỉ timeline, không marker (không vỡ).

---

## 1. Mục tiêu & bối cảnh (vì sao làm)

Khi hệ thống trả lời xong một câu hỏi lịch sử, ta muốn render **timeline** (dòng thời
gian) + **map** (bản đồ VN) cho các sự kiện liên quan. Dữ liệu hiện có **không dùng
được** cho việc này:

1. **Mất ràng buộc when–where–what.** Metadata mỗi chunk lưu `times`, `locations`,
   `events` thành **3 list phẳng rời nhau** (vd chunk `lichsu_clean-000001`:
   `times=[1859,1861,1862-03,1862-06-05,1862-12-16]`,
   `locations=[Gia Định, Gò Công, Sài Gòn]`). Không biết mốc nào gắn nơi nào → không
   chấm được điểm lên bản đồ.
2. **Phân mảnh sự kiện.** Một sự kiện lớn (vd Điện Biên Phủ) trải hàng chục chunk →
   vẽ theo từng chunk ra marker vụn, trùng.
3. **Chưa có toạ độ.** Địa danh chỉ là chữ ("Gia Định", "Đông Khê"), chưa có lat/lon.

Metadata phẳng hiện tại **giữ nguyên** (phục vụ retrieval/rerank — không đụng). Plan
này thêm **một lớp dữ liệu mới song song**: kho "atomic event" đã ràng buộc đủ
when–where–what + bảng toạ độ địa danh, dựng **offline 1 lần**; lúc trả lời chỉ **lọc
& ráp online** (không trích lại) → nhanh, ổn định, không hallucinate. Đúng contract
trong `CLAUDE.md` ("metadata extract offline / visualization sinh online từ events đã
retrieve") và quy tắc honest (thiếu data → không ép marker).

Chi phí API extract lại **không phải ràng buộc** (đã xác nhận với user).

---

## 2. Kiến trúc tổng (2 giai đoạn)

**Offline — 3 BƯỚC RỜI, chạy & verify độc lập (chốt 2026-06-22):**
```
[BƯỚC 1] run_segmentation.py:   chunks_llm.json ──► UNIT hoá (segmenter) ──► dataset/timeline_units.json
                                                                  └──── VERIFY phân đoạn ở đây ────┘
[BƯỚC 2] run_timeline_index.py: timeline_units.json ──► Extract LLM (mỗi unit → atomic event)
   │                             cache: dataset/timeline_extractions.json (resume theo unit_id+version)
   │                             ──► Reconcile (dedup + event_id) ──► Postgres: timeline_events ◄ source of truth
   ▼
[BƯỚC 3] build_gazetteer.py:    timeline_events.locations ──► Geocode (Google→LLM) ──► Postgres: gazetteer
                                 (⚠ TẠM HOÃN — làm cuối; xem note ưu tiên đầu file)
```
Ba bước nối nhau qua FILE (units.json → extractions.json → DB), nên verify xong bước
trước mới chạy bước sau; bước 2 đọc lại `timeline_units.json` thay vì tự gom (đảm bảo
trích đúng units đã verify).

**Online (khi trả lời user):** answer xong → biết `retrieved_chunk_ids` → lấy event có
`source_chunk_ids` giao với tập đó → join `gazetteer` lấy toạ độ → trả payload map +
timeline (link nhau bằng `event_id`). **KHÔNG trích mới.**

```
retrieved_chunk_ids ─► SELECT * FROM timeline_events WHERE source_chunk_ids && retrieved
                    ─► normalize_name(locations[]) ─► JOIN gazetteer ─► lat/lon
                    ─► tách: map markers (có lat/lon) + timeline items (có time)
                    ─► link 2 chiều bằng event_id ─► honest fallback
```

---

## 3. Database schema (Postgres)

Mirror đúng pattern `rag_chunks` trong
[chunk_store.py](../../apps/agent-service/app/tools/graph_rag/chunk_store.py):
`CREATE TABLE IF NOT EXISTS`, `_database_url()` strip `+psycopg`, GIN index cho mảng.

### Bảng 1: `timeline_events` (kho atomic event — source of truth) — ✅ ĐÃ TẠO

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `event_id` | `TEXT PRIMARY KEY` | Khoá ổn định = `uuid5(NS, norm_parent + '\|' + norm_time + '\|' + norm_location0 + '\|' + norm_label)`. Có `parent` trong khoá để tránh va chạm 2 sự kiện khác chiến dịch trùng time+nơi+label. Cùng nội dung → cùng id (idempotent, **không ngẫu nhiên**). Link map ↔ timeline. |
| `label` | `TEXT NOT NULL` | Tên sự kiện ngắn (vd "Ký Hiệp ước Nhâm Tuất"). |
| `summary` | `TEXT NOT NULL` | 1–2 câu mô tả, làm tooltip. |
| `time_start` | `TEXT` | ISO rút gọn: `YYYY` \| `YYYY-MM` \| `YYYY-MM-DD`. NULL nếu không xác định. (Độ chính xác suy ra từ format này, không lưu riêng.) |
| `time_end` | `TEXT` | Mốc kết thúc nếu là khoảng (chiến dịch); NULL nếu là điểm. |
| `locations` | `TEXT[] NOT NULL DEFAULT '{}'` | Địa danh (surface form); **`locations[0]` là địa điểm chính** để chấm marker. Builder `normalize_name` từng phần tử trước khi tra `gazetteer`. |
| `confidence` | `TEXT NOT NULL` | `cao` \| `vừa` \| `thấp` (đồng bộ `AliasVerdict`). Đã **gộp explicit/inferred**: suy từ ngữ cảnh → thấp hơn. Render đậm/nhạt theo trường này. |
| `parent_event_norm` | `TEXT` | `norm_name` của sự kiện vĩ mô (vd "khởi nghĩa trương định"); NULL nếu rời. Gom các dòng atomic cùng một sự kiện lớn + link sang Sự kiện node Neo4j. Tái dùng `resolve()`. |
| `source_chunk_ids` | `TEXT[] NOT NULL` | Provenance + **khoá join online**. |
| `created_at` / `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Audit. |

Index:
```sql
CREATE INDEX timeline_events_chunks_gin    ON timeline_events USING GIN (source_chunk_ids); -- query online chính
CREATE INDEX timeline_events_locations_gin ON timeline_events USING GIN (locations);
CREATE INDEX timeline_events_time_idx      ON timeline_events (time_start);
CREATE INDEX timeline_events_parent_idx    ON timeline_events (parent_event_norm);
```
Query online cốt lõi: `SELECT * FROM timeline_events WHERE source_chunk_ids && %s::text[]`
(toán tử `&&` = mảng giao nhau, chạy GIN index). `ORDER BY time_start NULLS LAST`.

**Cách ghi**: `replace_timeline_events()` = **TRUNCATE rồi insert trọn bộ** (KHÔNG upsert
lẻ) — tránh dòng rác khi re-extract đổi `event_id`; rẻ vì phần đắt (LLM) đã cache. Câu
INSERT có `ON CONFLICT (event_id) DO UPDATE` làm **lưới an toàn** chống trùng id trong
cùng mẻ (reconcile gộp sót → ghi đè thay vì crash).

### Bảng 2: `gazetteer` (địa danh → toạ độ) — ✅ ĐÃ TẠO

| Cột | Kiểu | Ý nghĩa |
|---|---|---|
| `location_norm` | `TEXT PRIMARY KEY` | `normalize_name(location)` — khoá dedup + join với `timeline_events.locations`. |
| `display_name` | `TEXT NOT NULL` | Tên hiển thị canonical. |
| `lat` | `DOUBLE PRECISION` | Vĩ độ; NULL nếu không định vị → location đó chỉ lên timeline, không marker. |
| `lon` | `DOUBLE PRECISION` | Kinh độ; NULL nếu không định vị. |
| `confidence` | `TEXT NOT NULL` | `cao` \| `vừa` \| `thấp` → render đậm/nhạt marker. |
| `created_at` / `updated_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Audit. |

**Cách ghi**: `upsert_gazetteer()` = `ON CONFLICT (location_norm) DO UPDATE` (build dần,
khoá ổn định). Khác `timeline_events` vì vòng đời khác: gazetteer cập-nhật-hoặc-thêm
từng địa danh, không nạp lại cả bảng.

### Đã CẮT khỏi schema (suy-ra-được / chỉ-phục-vụ-index / review)
- `timeline_events`: `time_precision` (suy từ format), `time_basis` (gộp vào confidence),
  `primary_location` (dùng `locations[0]`), `heading_path` (suy qua chunk),
  `unit_id`/`extracted_prompt_version` (để trong cache json), `metadata` JSONB.
- `gazetteer`: `admin_level`, `modern_name`, `aliases[]`, `resolved_by`, `note` — thông
  tin review để trong `dataset/gazetteer_review.md`, không vào DB.
- **Thêm sau khi cần (MVP chưa làm):** `timeline_events.actors TEXT[]`.

---

## 4. Mô hình "1 sự kiện nhiều mốc / nhiều nơi"

Đơn vị mỗi dòng = **1 atomic event = 1 mốc thời gian + (các) địa điểm của mốc đó**.
- **Nhiều địa điểm cùng lúc** → để hết trong `locations[]`; render nhiều marker **chung
  `event_id`**. `locations[0]` là nơi chính.
- **Khoảng thời gian liên tục** → `time_start` + `time_end`.
- **Nhiều mốc rời rạc của cùng một sự kiện lớn** → tách thành **nhiều dòng** (mỗi mốc 1
  điểm timeline / 1 marker), tất cả chung `parent_event_norm` để gom nhóm/tô màu/collapse.
- **Honest fallback**: thiếu location → chỉ timeline; thiếu time → chỉ map; thiếu cả hai
  → không marker.

---

## 5. Lớp "unit" để trích — ĐÃ CHỐT: HƯỚNG A ✅

Mục tiêu: gom văn bản thành "unit" đủ context cho LLM trích atomic event.

**Quyết định (chốt 2026-06-20)**: dùng **Hướng A (segmenter), cap 50K**. Lý do: boundary
unit là yếu tố bậc 2 với chất lượng trích — reconcile (dedup) + `parent_event_norm` đã
gom nhóm ở tầng dữ liệu, và completeness pass chống sót ở unit lớn. Hướng B (tách file
tay) fork corpus → prose lệch khỏi text đã embed → gãy provenance ("có căn cứ"), nên chỉ
dùng làm **spot-fix** cho section nào A chứng minh lump/split tệ, không thay hẳn.

### Hướng A — Segmenter tự gom heading (✅ ĐÃ BUILD + CHỐT)
[segmenter.py](../../apps/agent-service/app/indexing/timeline/segmenter.py):
`build_units(chunks, cap=50K)`. Đệ quy "shallowest-fit": gom trọn section nếu ≤ CAP,
không thì chia sâu theo cấp heading, hết heading mà vẫn > CAP thì cắt theo chunk +
overlap. **Đo thật cap 50K**: 186 unit, vẫn gom theo heading (`chunk_split` không kích
hoạt — overlap=0), median ~7.3K ký tự, max ~49.7K, phủ đủ 1213/1213 chunk. Cap 50K là
điểm tối ưu đo thật: lớn nhất mà 0 unit vượt ~15K token (vùng recall LLM yếu) VÀ chưa
phải cắt cứng. Test: [test_segmenter.py](../../apps/agent-service/tests/test_segmenter.py).

- ✅ Tự động, tất định, re-run được; đọc đúng chunk đã embed (không fork corpus). ❌
  Boundary do thuật toán quyết → vài unit lớn (top ~10%, > ~40K chữ) có completeness pass
  ở extractor làm lưới chống sót.

### Hướng B — Tách sẵn file .md, người kiểm soát (❌ KHÔNG dùng làm mặc định; giữ làm spot-fix)
Tách `lichsu.clean.md` thành cây file `.md` con (mỗi file ~1 chiến dịch) để **người
curate**. Hệ thống đọc mỗi file = 1 unit, không tự gom heading nữa. *Đã loại làm mặc
định (xem lý do ở đầu §5: fork corpus phá provenance); chỉ cân nhắc cho 1-2 section nếu
A lump/split tệ rõ rệt.*

**Scheme thư mục** (theo file mẫu user mở):
`dataset/{thời kỳ}/{NN-cuộc chiến}/{NN-chiến dịch}.md`, prefix số để sắp thứ tự,
phân tách bằng ` — `.

**Hệ quả kỹ thuật QUAN TRỌNG — giữ khoá join online:** online join cần
`source_chunk_ids`. Mỗi file .md là một lát của `lichsu.clean.md`; chunk cũng có
`start_line`/`end_line` trỏ về `lichsu.clean.md`. → Map mỗi file → chunk_ids bằng
**giao khoảng dòng** (mỗi chunk gán vào section chứa dòng đầu của nó → mỗi chunk thuộc
đúng 1 section). Lưu linkage vào **frontmatter** của file .md:
```yaml
---
section_id: thoi-ky-cong-hoa/03-chien-tranh-dong-duong/03-cac-no-luc-ngoai-giao
heading_path: ["Thời kỳ cộng hoà", "3. Chiến tranh Đông Dương", "Giai đoạn 1946-1949", "Các nỗ lực ngoại giao"]
source_lines: [1091, 1102]
source_chunk_ids: ["lichsu_clean-000NNN", ...]
---
```
Người sửa prose tự do (không đổi linkage). Nếu re-split file → cập nhật frontmatter
(hoặc chạy lại script remap theo dòng).

### Phân tích granularity (đo thật trên nhánh "3. Chiến tranh Đông Dương", 630K ký tự)
Cấu trúc nguồn **không đều**: "1 chiến dịch" nằm ở **h2** (khởi nghĩa nhỏ), **h3**
(Hương Khê), hoặc **h4** (Điện Biên Phủ, Biên giới...). Dưới chiến dịch, h5/h6 thường
chỉ là **bộ phận** (Diễn biến / Kết quả / Bối cảnh / Lập trường của X).

Mô phỏng các rule (số file CHỈ cho riêng nhánh Đông Dương):
| Rule | Số file | Vấn đề |
|---|---|---|
| size-descent TARGET=6K | 78 | Vỡ vụn: tách cả "Diễn biến"/"Kết quả"/"Lập trường của Anh/Lào/..." thành file riêng. |
| size-descent TARGET=10K | 72 | Vẫn vỡ vụn ở h5/h6. |
| size-descent TARGET=20K | 67 | Vẫn nhiều mảnh h5/h6 (vì h4 chiến dịch lớn vẫn > 20K → descend tiếp). |
| mọi leaf heading = file | 78 | Vỡ vụn nhất. |

**Kết luận**: **không** rule size/depth thuần nào cho ra đúng "1 chiến dịch/file". Rule
size-descent over-fragment vì cứ > target là descend xuống h5/h6 (vốn là bộ phận). Rule
hứa hẹn hơn: **"cắt ở ĐỘ SÂU chiến dịch (dừng ở h4), luôn inline h5/h6 vào file cha,
chấp nhận vài file lớn"** — nhưng độ sâu chiến dịch thay đổi (h2/h3/h4) nên vẫn cần
người chỉnh. → Đây chính là lý do user muốn curate tay. Script chỉ sinh **first-cut**.

### Quyết định đã chốt (2026-06-20)
1. **Unit hoá**: dùng Hướng A (segmenter), KHÔNG tách file tay. ✅
2. **Cap**: 50K ký tự (đo thật, xem trên). ✅
3. **Completeness pass**: bật cho unit > 40K chữ ở extractor (chống sót đuôi context). ✅
4. Phần granularity/frontmatter của Hướng B (mục cũ) chỉ còn ý nghĩa tham khảo nếu sau
   này cần spot-fix tay 1-2 section — không triển khai đại trà.

---

## 6. Code modules + trạng thái

### ✅ Đã build (Phase 1)
- [app/schemas/timeline.py](../../apps/agent-service/app/schemas/timeline.py) —
  `AtomicEvent` (label, summary, time_start, time_end, locations, parent_event,
  confidence) + `TimelineExtraction`. Strict mode, dùng `""`/`[]` cho "không có".
- [app/schemas/gazetteer.py](../../apps/agent-service/app/schemas/gazetteer.py) —
  `GeocodeResult` (lat, lon, confidence, admin_level, modern_name, note). 3 field cuối
  chỉ vào review, không vào DB.
- [app/tools/visualization/event_store.py](../../apps/agent-service/app/tools/visualization/event_store.py)
  — DDL `timeline_events` + 4 index + `ensure/replace_timeline_events/select_events_by_chunks`.
- [app/tools/visualization/gazetteer_store.py](../../apps/agent-service/app/tools/visualization/gazetteer_store.py)
  — DDL `gazetteer` + `ensure/upsert_gazetteer/lookup_coords`.
- *Verify*: smoke test trên Postgres thật OK (TRUNCATE+insert, `&&` join, ""→NULL,
  đa địa điểm, gazetteer NULL lat/lon). ruff + mypy sạch.

### ✅ Đã build (Phase 2)
- [app/indexing/timeline/segmenter.py](../../apps/agent-service/app/indexing/timeline/segmenter.py)
  + [tests/test_segmenter.py](../../apps/agent-service/tests/test_segmenter.py) — xem §5
  Hướng A (đã chốt dùng, cap 50K). 6/6 test pass. **Tách bước 1 (2026-06-22)**:
  `scripts/run_segmentation.py` chạy/verify phân đoạn độc lập (ghi `dataset/timeline_units.json`
  + report phủ chunk / overlap / độ dài / unit lớn); `segmenter.py` thêm `unit_to_dict`/
  `unit_from_dict`; bước 2 (`run_timeline_index.py`) đọc lại artifact thay vì tự `build_units`.

### ✅ Đã build (Phase 4)
- [app/prompts/timeline_extract.py](../../apps/agent-service/app/prompts/timeline_extract.py)
  — `TIMELINE_PROMPT_VERSION = "timeline-extract-v1"`, self-contained: chỉ lấy sự kiện CÓ
  DIỄN BIẾN; ràng buộc đúng mốc–nơi; **anchor inheritance** (suy năm → hạ confidence);
  honest (rỗng nếu chỉ là đánh giá); `parent_event` gom nhóm; `locations[0]` chính.
  Few-shot Trương Định / Biên giới.
- [app/indexing/timeline/atomic_event_extractor.py](../../apps/agent-service/app/indexing/timeline/atomic_event_extractor.py)
  — `extract_timeline_events(text, heading_path, *, client, model, unit_id)`, khung copy
  từ entity_relation_extractor: `.parse(response_format=TimelineExtraction, temperature=0.0,
  timeout=60)`, xử lý refusal. **Completeness pass** cho unit > 40K chữ (hỏi lại kèm danh
  sách label đã có, dedup theo `(label, mốc, địa điểm chính)`). Dùng `timeline_llm_model`
  (config mới) fallback `llm_model`.
- *Verify*: trích thử 2 unit đầu (Trương Định + Nguyễn Hữu Huân) qua gateway `cx/gpt-5.4`:
  34 event, 0 event thiếu cả time lẫn location; "5/6/1862 ký Hiệp ước Nhâm Tuất" → cao;
  câu kế thừa năm → vừa/thấp; đa địa điểm cùng mốc gộp 1 event; parent_event sạch.

### ✅ Đã build (Phase 5)
- [app/indexing/timeline/reconcile.py](../../apps/agent-service/app/indexing/timeline/reconcile.py)
  + [tests/test_reconcile.py](../../apps/agent-service/tests/test_reconcile.py) —
  `reconcile_events(cache) -> records`: `event_id = uuid5(NS, norm_parent|norm_time|
  norm_location0|norm_label)` tất định; dedup xuyên unit (hợp nhất `source_chunk_ids` +
  `locations`, giữ confidence cao nhất); `parent_event_norm = resolve()` (link Sự kiện
  Neo4j). THUẦN, không LLM.
- [scripts/run_timeline_index.py](../../apps/agent-service/scripts/run_timeline_index.py)
  — bổ sung stage **reconcile → load DB** (`replace_timeline_events`). Flags thêm
  `--skip-reconcile --skip-db --allow-empty`; `--limit -1` = chỉ reconcile + nạp DB từ
  cache. **Guard**: reconcile ra 0 event → KHÔNG nạp (tránh TRUNCATE xoá trắng bảng),
  trừ khi `--allow-empty`.
- *Verify*: nạp 34 event vào `timeline_events`; 34/34 distinct event_id (không trùng);
  0 dòng `source_chunk_ids` rỗng; 28 có `parent_event_norm`; join online
  `select_events_by_chunks(['lichsu_clean-000000'])` → 15 event đúng; guard chống wipe
  test OK (artifact sai → bảng giữ nguyên 34). ruff + mypy sạch, 17/17 test pass.
- *Code-review (`/code-review`) — đã verify lại từng finding bằng chạy thật*:
  - **2 bug THẬT đã sửa**: (1) `replace_timeline_events([])` TRUNCATE-wipe bảng khi cache
    rỗng — mất dữ liệu (code TRUNCATE vô điều kiện) → thêm guard ở runner, bắt buộc
    `--allow-empty`; (2) dedup completeness chỉ-theo-label làm RỚT sự kiện cùng tên khác
    mốc → đổi key `(label,mốc,nơi)` (verify: key cũ giữ 0/1, key mới 2/2).
  - **1 DƯƠNG TÍNH GIẢ**: ".format vỡ với `{}`" — str.format không parse lại giá trị chèn
    (đã test). f-string giữ lại chỉ vì gọn hơn, KHÔNG phải sửa lỗi.
  - **2 cải tiến phòng thủ (không phải bug đang xảy ra)**: `timeline_llm_model` knob cho
    nhất quán với graph (model hiện tại cx/gpt-5.4 vẫn chạy tốt); log refusal cho dễ thấy
    (hành vi cache-khi-refusal giữ nguyên như graph extractor).

### ✅ Đã build (Phase 6) — Geocoding HYBRID (Google + LLM)
> **Cập nhật 2026-06-22**: đổi provider **Mapbox → Google Geocoding API** (user đã có
> Google Maps key). Adapter tách rời nên chỉ thay `_mapbox_geocode()` → `_google_geocode()`
> đúng như §9 dự liệu. Logic hybrid/name-gate/bbox giữ nguyên. Tài liệu API:
> [docs/reference/google-maps-api.md](../reference/google-maps-api.md).
- [app/indexing/geocoding/geocoder.py](../../apps/agent-service/app/indexing/geocoding/geocoder.py)
  — `geocode_location(name) -> GeocodeOutcome` **hybrid: Google trước, LLM fallback**.
  Google Geocoding (`region=vn` chỉ BIAS, **KHÔNG ép country** — địa danh nước ngoài như
  Paris/Genève/Trung Quốc vẫn geocode được) cho địa danh còn tên; **name-gate** (so token
  tên bỏ dấu + i/y với `formatted_address`) loại fuzzy-match (Google trả "đại khái" 1 kết
  quả, cờ `partial_match`) -> rơi xuống LLM. Confidence suy từ `types` (country→thấp,
  administrative_area_level_1→vừa, còn lại→cao). KHÔNG lọc bbox VN (helper `in_vietnam`
  giữ lại cho UI).
- [app/prompts/geocode.py](../../apps/agent-service/app/prompts/geocode.py) —
  `GEOCODE_PROMPT_VERSION`, prompt LLM suy lat/lon + confidence + modern_name cho địa
  danh lịch sử VN (0.0/0.0 = không định vị được -> honest).
- [app/schemas/gazetteer.py](../../apps/agent-service/app/schemas/gazetteer.py) — thêm
  `GeocodeOutcome` (hợp nhất Google/LLM, `resolved_by ∈ {google,llm,none}`).
  `config.google_maps_api_key`.
- [scripts/build_gazetteer.py](../../apps/agent-service/scripts/build_gazetteer.py) —
  đọc địa danh từ `timeline_events.locations` (qua `select_location_counts`), geocode
  (cache `dataset/gazetteer.json`, resume), upsert `gazetteer`, sinh `gazetteer_review.md`.
  Flags `--limit --workers --min-count --overwrite --skip-db`.
- *Verify thật (trước khi đổi, 31 địa danh từ 2 unit)*: **18 Mapbox + 12 LLM + 1 honest
  "none"**. Name-gate sửa được các fuzzy-match (Chợ Lớn→Q5, Sơn Trà→Đà Nẵng, Rạch Tra→Củ
  Chi, Bình Cách→Tiền Giang). Join end-to-end OK: event→locations→gazetteer→markers; event
  thiếu địa điểm → chỉ-timeline. Còn lại trùng-tên-khác-tỉnh (Định Tường→Thanh Hóa…) cần
  review tay. 12/12 test geocoder pass, ruff+mypy sạch. *Cache `gazetteer.json` hiện vẫn
  giữ toạ độ nguồn Mapbox (vẫn hợp lệ); chạy `build_gazetteer.py --overwrite` để geocode
  lại toàn bộ bằng Google nếu muốn đồng nhất nguồn.*

### ✅ Đã build (Phase 7) — Builder online
- [app/schemas/visualization.py](../../apps/agent-service/app/schemas/visualization.py)
  — `MapMarker`, `TimelineItem`, `VisualizationPayload`. Map↔timeline link bằng `event_id`.
- [app/tools/visualization/builder.py](../../apps/agent-service/app/tools/visualization/builder.py)
  — **online** `build_visualization(retrieved_chunk_ids) -> VisualizationPayload`:
  `select_events_by_chunks` → `normalize_name(locations)` → `lookup_coords` (gazetteer) →
  tách markers (có toạ độ) + timeline items (có time), link `event_id`, honest fallback
  (thiếu nơi→chỉ timeline; thiếu time→chỉ map; thiếu cả→`unplaced_count`). Marker
  confidence = YẾU NHẤT giữa event và toạ độ (đậm/nhạt). KHÔNG trích mới.
- *Verify thật* (chunk Trương Định): 15 event → 23 marker + 15 timeline; 12 event có cả
  hai (link 2 chiều), 3 chỉ-timeline (không toạ độ); confidence lan đúng. 8/8 test pass.
- *Deferred*: bộ LỌC LLM "event nào answer thực sự nhắc tới" (plan đề tuỳ chọn) — dành
  khi tích hợp answer flow của agent (chưa có `answer_text` ở giai đoạn này).

### 🔜 Chưa build
- Cập nhật `scripts/reset_stores.py` thêm tuỳ chọn drop 2 bảng mới.
- Tích hợp builder vào answer flow agent + (tuỳ chọn) LLM relevance filter.

### File cache (mirror `graph_extractions.json`, atomic write `os.replace`)
- `dataset/timeline_units.json` — envelope `{cap, source_file, count, units:[...]}` do BƯỚC 1
  (`run_segmentation.py`) ghi; BƯỚC 2 đọc lại (KHÔNG tự build). Là nơi verify phân đoạn.
- `dataset/timeline_extractions.json` — `{unit_id: {prompt_version, heading_path,
  source_chunk_ids, events:[...]}}`. Resume: bỏ qua unit có version khớp.
- `dataset/gazetteer.json` — cache geocode `{location_norm: {...}}`.
- `dataset/gazetteer_review.md` — top-N địa danh tần suất cao + confidence thấp, review tay.

---

## 7. Thứ tự build (phases) + tiến độ

1. ✅ **Schema + storage + DDL** (không tốn API).
2. ✅ **Segmenter** (Hướng A, cap 50K) — đã chốt dùng.
3. ✅ **[NGÃ RẼ §5] đã chốt**: dùng Hướng A, không tách file tay (xem §5).
4. ✅ **Prompt + extractor + `run_timeline_index.py`** — đã build, trích thử Trương Định
   + Nguyễn Hữu Huân OK (xem §6 Phase 4, §8).
5. ✅ **Reconcile + load DB** — event_id tất định, dedup, parent_norm; nạp 34 event vào
   `timeline_events`, join online OK (xem §6 Phase 5, §8).
6. ✅ **Geocoder (Google+LLM) + `build_gazetteer.py`** — 31 địa danh đã vào `gazetteer`,
   join event→toạ độ OK (xem §6 Phase 6, §8). Còn review tay vài địa danh trùng tên.
   *(Provider đổi Mapbox→Google 2026-06-22.)*
7. ✅ **Builder online** + `schemas/visualization.py` — payload map+timeline link bằng
   event_id, honest fallback; verify chunk Trương Định (15 event → 23 marker + 15 item).
8. 🔜 **Chạy full corpus** + tích hợp builder vào answer flow agent. *(kế tiếp)*

---

## 8. Verification

- ✅ **Schema/storage**: smoke test DB thật (xem §6 Phase 1).
- ✅ **Segmenter** (cap 50K): 186 unit, 0 cắt cứng (overlap=0), phủ đủ 1213 chunk, 6/6 test pass.
- ✅ **Extract (limit nhỏ)**: 2 unit đầu (Trương Định + Nguyễn Hữu Huân) → 34 event, mỗi
  event đúng bộ ba when–where–what; "5/6/1862 ký Hiệp ước Nhâm Tuất" → cao; câu kế thừa
  năm/suy ngữ cảnh → vừa/thấp; honest fallback (0 event thiếu cả time+location); đa địa
  điểm cùng mốc gộp 1 event; parent_event gom nhóm sạch.
- ✅ **DB sau index**: nạp 34 event; 34/34 distinct event_id (không trùng); 0 dòng
  `source_chunk_ids` rỗng; 28 dòng có `parent_event_norm`. Guard chống TRUNCATE-wipe khi
  cache rỗng đã test OK.
- ✅ **Builder online (`build_visualization`)**: chunk Trương Định → 15 event → 23 marker
  + 15 timeline item, unplaced=0; 12 event có cả marker+timeline (link 2 chiều bằng
  event_id), 3 chỉ-timeline (thiếu toạ độ); marker confidence = yếu nhất (event ∧ toạ độ);
  đa địa điểm → nhiều marker chung event_id. 8/8 test pass.
- 🟡 **Gazetteer**: 31 địa danh (18 Mapbox / 12 LLM / 1 none). Spot-check OK cho địa danh
  rõ; còn vài địa danh TRÙNG TÊN khác tỉnh (Định Tường→Thanh Hóa, Tân Hòa→Đồng Nai) và 1
  LLM-miss (Làng Tịch Hà→Huế) cần sửa tay trong `gazetteer.json` rồi chạy lại.
- **Lint/type/test**: `ruff` + `mypy` + `pytest` (chạy bằng root venv
  `.\venv\Scripts\python.exe`).

---

## 9. Quyết định mặc định đã chốt (đổi được)
- **Geocoding = Google-trước + LLM-fallback + review tay** — **⚠️ TẠM HOÃN (2026-06-22):
  làm cuối, tạm KHÔNG chạy; xem note ưu tiên đầu file.** (đổi từ Mapbox sang Google
  2026-06-22; quyết định gốc Mapbox chốt 2026-06-21). Google Geocoding (`region=vn` chỉ
  BIAS, **KHÔNG ép chỉ-Việt-Nam** — corpus có địa danh nước ngoài: Paris/Genève/Trung
  Quốc/đảo Rêuyniông... cần geocode đúng) cho địa danh còn tên (chính xác); name-gate loại
  fuzzy-match → LLM lo địa danh lịch sử/đổi tên/biến mất. (Loại OSM/Nominatim thuần vì phủ
  kém.) Provider tách rời → đổi chỉ thay 1 adapter (`_google_geocode()`), đã chứng minh khi migrate.
  *Điểm yếu còn lại: địa danh TRÙNG TÊN khác tỉnh (Định Tường→Thanh Hóa) provider chấm sai
  mà vẫn "cao" → review tay bắt; ý tưởng sau: regional sanity-check / LLM disambiguate
  top-N candidate.* **⚠️ ToS Google: cache lat/lon ≤ 30 ngày** (place_id lưu vô hạn);
  `gazetteer.json`/bảng `gazetteer` lưu lâu hơn là rủi ro tuân thủ — xem
  [docs/reference/google-maps-api.md](../reference/google-maps-api.md) §4.
- **Lưu Postgres**, không tạo node Neo4j mới; link graph bằng `parent_event_norm`.
- Thang `confidence` tiếng Việt `cao/vừa/thấp` (đồng bộ `AliasVerdict`).
- `event_id` = uuid5 tất định (idempotent), KHÔNG ngẫu nhiên.
- Map render = Google Maps JavaScript API (AdvancedMarkerElement), dùng `GOOGLE_MAPS_API_KEY`.
  POC: `google_map_test.py` (root), `scripts/show_google_map.py`. *(TrackAsia
  `trackasia-map-test.html` còn lại làm tham khảo; đã chuyển hẳn sang Google.)*

---

## 10. Số liệu nguồn (tham chiếu)
- `lichsu.clean.md`: 7.623 dòng, ~3.1MB. Heading: **3 h1, 33 h2, 75 h3, 106 h4, 140
  h5, 84 h6**.
- 3 h1: "Thời kì thuộc địa", "Nhật thuộc", "Thời kỳ cộng hoà".
- `chunks_llm.json`: 1213 chunk, `chunk_index` 0..1212 liền mạch, `source_file =
  lichsu.clean.md`, có `start_line`/`end_line` (trỏ về lichsu.clean.md) → dùng map chunk
  ↔ section file.
- Section to nhất: "5. Kháng chiến chống Mỹ" (~4245 dòng), "3. Chiến tranh Đông Dương"
  (~1835 dòng / 630K ký tự).
