# Plan: Trang "Dòng thời gian" (Timeline Explorer)

**Trạng thái**: chưa code. Chốt thiết kế 2026-07-20 · **soát lại + đo lại 2026-09-01**.

Trang **độc lập, KHÔNG liên quan hỏi đáp** — không gọi agent-service, không tốn LLM call
nào, không đụng orchestrator. Chỉ đọc `timeline_events` + `rag_chunks` đã index sẵn.

> **⚠️ Cập nhật 2026-09-01 — bản 07-20 đã lệch thực tế ở 5 chỗ** (corpus đổi sang
> `tap1/tap2/tap3.clean.md`, commit fd1cb70 cho phép mốc TCN + thế kỷ, layout đổi):
>
> 1. **Số liệu**: 3.674 → **3.800** event, 2.984 → **3.176** có mốc (§2).
> 2. **Thời kỳ**: 3 chương → **11 PHẦN** trải từ nguyên thuỷ đến 2006 → badge đổi hẳn,
>    và bộ lọc 3 chip của bản cũ bỏ luôn (§2, §4.3).
> 3. **`ORDER BY time_start ASC` GIỜ SAI**: dữ liệu đã có `179 TCN`, `XII`, `40` → sort
>    chuỗi xếp sai hẳn. Thêm cột `time_sort` (§3.1, đã chốt).
> 4. **`TimelineBar` hiện tại đang lỗi im lặng** với chính mấy mốc đó (§4.4) — sửa luôn
>    khi tách `timeFormat.ts`.
> 5. **`root: null` không chạy**: `AppShell` là `h-screen overflow-hidden` nên cửa sổ
>    không cuộn; trang phải tự có khung cuộn (§4.2).

## 1. Mục tiêu

Cho người dùng một cái nhìn trực quan, liên tục về dòng chảy lịch sử — từ thời dựng nước
đến sau đổi mới — bày **timeline so le hai bên một trục dọc**, cuộn xuống thì nạp thêm mốc.
Đây là chỗ DUY NHẤT phía user chạm được tới chiều rộng của kho tri thức (hiện 3.176 sự kiện
có thời gian chỉ hiện ra nhỏ giọt ~5-10 cái mỗi câu trả lời, hoặc phải là admin mới xem được
qua KB Inspector).

Tham chiếu hình thức: timeline so le của các trang sử phổ thông (thẻ trái/phải xen kẽ, trục
dọc ở giữa, mỗi thẻ có nhãn thời kỳ). **Không** bê nguyên: xem mục 5.

## 2. Dữ liệu — đo lại 2026-09-01

> Nguồn đo: `dataset/timeline_extractions.json` + `dataset/chunks_llm.json` (bộ chính hiện
> tại = `tap1/tap2/tap3.clean.md`, 1.212 chunk). **Chưa đối chiếu được với Postgres** —
> `localhost:5432` timeout, docker chưa chạy. Con số dưới là **trước** bước reconcile;
> dedup theo `event_id` tất định sẽ bớt vài chục dòng, không đổi bức tranh.

| Chỉ số | 07-20 (cũ) | **09-01 (thật)** |
|---|---|---|
| Event tổng | 3.674 | **3.800** |
| Có `time_start` | 2.984 | **3.176** (624 không có mốc → KHÔNG lên trang này) |
| Có `time_end` | 356 (12%) | **390** (12%) |
| Số năm SCN phân biệt | 102 | **~610** |
| `confidence` | cao 2.568 · vừa 1.099 · thấp 7 | **cao 2.809 · vừa 991 · thấp 0** |
| Có mốc nhưng **không có địa điểm** | (không đo) | **1.431 (45%)** |

**Độ mịn `time_start`** (3.176 mốc):

| Dạng | Số | Ví dụ |
|---|---|---|
| Ngày `YYYY-MM-DD` | 969 | `1954-05-07` |
| Tháng `YYYY-MM` | 597 | `1856-09` |
| Năm | 1.525 | `1945` · **`40`** (15 mốc 2 chữ số) · `938` (~115 mốc 3 chữ số) |
| Thế kỷ La Mã (SCN) | 61 | `XII`, `XIX` |
| Năm TCN | 18 | `179 TCN`, `111 TCN` |
| Thế kỷ TCN | 5 | `VII TCN`, `III TCN` |
| **Rác** | **1** | `9 tháng` (LLM lấy độ dài làm mốc) |

> Cache `timeline_extractions.json` đang được chạy lại (đo lúc 22:05 ngày 01-09: 1.212 chunk).
> Con số nhích vài chục mỗi lần chạy — coi là ảnh chụp, không phải hằng số.

Rác `9 tháng` xuất hiện 2 chỗ: `time_start` của event "Đông Kinh nghĩa thục hoạt động trong
9 tháng" (`tap2_clean-000170`) và `time_end` của "Phổ biến Quốc dân độc bản"
(`tap2_clean-000166`). Không sửa dataset — trang này bỏ qua mốc không parse được (§3.1).

**Mật độ đều hơn hẳn bản cũ**: năm dày nhất là 1945 (88 event), rồi 1946 (74), 1975 (70) —
không còn cảnh 1954 chiếm 356 dòng. Theo thế kỷ: XX 1.617 · XIX 498 · XIII 196 · XVIII 169 ·
XV 154 · XI 103, còn lại rải mỏng về tới thế kỷ I.

**Nhãn thời kỳ (badge) vẫn lấy từ `rag_chunks.heading_path[1]`** (Postgres đánh số từ 1 →
phần tử đầu = `h1`). Metadata chunk giờ là `headings: {h1, h2, h3}`, nhưng
`tools/graph_rag/chunks.py::build_heading_path` vẫn dựng cột `heading_path TEXT[]` như cũ →
cách nối qua `source_chunk_ids` KHÔNG đổi. Nối thử sạch 100%, không sót event nào:

| Thời kỳ (`h1`) | Event có mốc | Tổng |
|---|---|---|
| PHẦN MỘT THỜI ĐẠI NGUYÊN THUỶ | 6 | 12 |
| PHẦN HAI THỜI ĐẠI DỰNG NƯỚC | 24 | 38 |
| PHẦN BA THỜI KÌ BẮC THUỘC VÀ CHỐNG BẮC THUỘC | 89 | 98 |
| PHẦN BỐN THỜI ĐẠI PHONG KIẾN DÂN TỘC | 1.063 | 1.368 |
| PHẦN MỘT VIỆT NAM (1858 - 1896) | 317 | 381 |
| PHẦN HAI VIỆT NAM (1897 - 1918) | 367 | 427 |
| PHẦN BA VIỆT NAM (1919 - 1930) | 215 | 244 |
| PHẦN BỐN VIỆT NAM (1930 - 1945) | 238 | 283 |
| PHẦN MỘT ... KHÁNG CHIẾN CHỐNG THỰC DÂN PHÁP ... (1945 - 1954) | 351 | 406 |
| PHẦN HAI ... XÂY DỰNG MIỀN BẮC ... (1954 - 1975) | 444 | 481 |
| PHẦN BA ... XÃ HỘI CHỦ NGHĨA (1975 - 2006) | 62 | 62 |
| **Tổng** | **3.176** ✓ | **3.800** ✓ |

## 3. Backend

Route mới, **chỉ cần đăng nhập** (không gác admin) — cùng lý do với
`GET /api/chat/sources/{chunk_id}`: corpus là SGK, không mật.

### 3.1. Khoá sắp xếp thời gian — CHỐT phương án A (2026-09-01)

Bản 07-20 viết: *"`time_start` là TEXT nhưng dạng ISO prefix nên sort chuỗi ĐÚNG thứ tự
thời gian, không cần cast"*. **Không còn đúng** từ commit fd1cb70: `179 TCN` sort cạnh năm
179 SCN, `XII` rơi xuống sau mọi chữ số, `40` đứng trước `1945`. Ảnh hưởng 99/3.176 mốc
(3,1%) — ít, nhưng chúng nằm rải đúng phần cổ sử vừa thêm, và sai thứ tự thì cả feed vô
nghĩa.

**Quy ước khoá** (chung cho cả 2 phương án) — số thực "năm thập phân", chỉ để SẮP XẾP,
không bao giờ hiển thị:

| `time_start` | Khoá | Ghi chú |
|---|---|---|
| `1954-05-07` | 1954,35 | `năm + (tháng-1)/12 + (ngày-1)/365` |
| `1856-09` | 1856,67 | |
| `1945` · `40` | 1945 · 40 | năm 1–4 chữ số như nhau |
| `XII` | 1101 | thế kỷ → năm ĐẦU thế kỷ |
| `179 TCN` | −179 | TCN → số âm (`179 TCN` đứng trước `111 TCN` ✓) |
| `III TCN` | −300 | thế kỷ TCN → năm đầu thế kỷ |
| `9 tháng` | NULL | không parse được → không lên trang |

Sắp xếp: `ORDER BY <khoá> ASC, label ASC`.

**CHỐT: thêm cột `time_sort` vào `timeline_events`.** Reconcile tính sẵn,
`event_store.py` thêm cột + index, backend chỉ việc `ORDER BY time_sort`.

- Sửa: `indexing/timeline/reconcile.py` (hàm `_time_sort()`), `tools/visualization/event_store.py`
  (DDL + INSERT + index), backend `models/timeline.py` dùng cột.
- Nạp lại bảng: `python scripts/run_timeline_index.py --limit -1` — **không gọi LLM**
  (đọc cache, reconcile, TRUNCATE + insert). Cần docker chạy.
- Lợi thêm: `event_store.py` truy vấn online cho thanh timeline bên câu trả lời cũng đang
  `ORDER BY time_start ASC` sai y hệt → sửa một lần được cả hai chỗ.

*Phương án đã cân nhắc rồi bỏ:* tính khoá bằng biểu thức `CASE ... regexp` ngay trong câu
query của backend — không đụng schema, không cần nạp lại DB, nhưng SQL dài khó đọc, cần
expression index nếu chậm, và thanh timeline bên câu trả lời VẪN sai.

### 3.2. `models/timeline.py` (mới)

```
list_timeline_cards(limit: int, offset: int) -> (rows, total)
```

- `WHERE time_start IS NOT NULL` + loại mốc không parse được (khoá NULL) → 624 event vô
  thời gian và mốc rác không lọt vào.
- `ORDER BY time_sort ASC, source_chunk_ids[1] ASC, label ASC` (§3.1). Chốt phụ:
  `source_chunk_ids[1]` (vd `tap2_clean-000358`) mang đúng **thứ tự đọc của sách** → các sự
  kiện cùng một mốc giữ nguyên mạch kể; sort theo `label` sẽ xáo thành thứ tự abc vô nghĩa.
- Era: `LEFT JOIN LATERAL` lấy `heading_path[1]` của chunk ĐẦU TIÊN trong
  `source_chunk_ids` (1 event hầu như nằm gọn trong 1 mục). `LEFT` để event có chunk lạ vẫn
  ra, badge rỗng — không nuốt mất dòng.
- Bắt `UndefinedTable` → trả `([], 0)` theo pattern `cost.py`.

### 3.3. `api/timeline.py` (mới)

- `GET /api/timeline/events?limit=30&offset=0` → `{items, total, limit, offset}`,
  khớp hình dạng `listEvents` hiện có để tái dùng `getNextPageParam`.
- Item gồm: `event_id, label, summary, time_start, time_end, locations, confidence, era`.
- **Trả luôn `summary` trong danh sách** (30 item/trang, không đáng kể) → click thẻ mở chi
  tiết inline mà KHÔNG cần endpoint detail riêng.
- **KHÔNG trả `source_chunk_ids`** — trang này không có nút xem nguồn (§4.2b). Cột đó chỉ
  dùng phía server để join era + sắp thứ tự đọc.
- Đăng ký router trong `main.py`; schema `schemas/timeline.py`.

## 4. Frontend

### 4.1. Khung file

- Route `/timeline` (`routes.tsx`, con của `AppShell`, ngang hàng `index: AskPage`).
- Mục nav thứ hai cho user trong `AppSidebar` (khu user hiện có đúng 1 route). **Đặt tên
  "Dòng lịch sử"**, KHÔNG dùng "Dòng thời gian" — nhãn đó đã thuộc mục admin
  `/admin/kb/timeline`, admin đăng nhập sẽ thấy 2 mục trùng tên.
- `api/timeline.ts` — `listTimelineCards`.
- `pages/TimelinePage.tsx` — wrapper mỏng + `PageHeader`.
- `features/explore/`: `TimelineSpine.tsx` · `TimelineCard.tsx`.
- Mobile (`< md`): trục dạt sang trái, mọi thẻ nằm bên phải (bố cục so le vỡ ở màn hẹp).

### 4.2. Cuộn — khung riêng, KHÔNG cuộn cửa sổ

`AppShell` là `h-screen overflow-hidden`, vùng nội dung cũng `overflow-hidden` → cửa sổ
không bao giờ cuộn. Nên `TimelinePage` tự dựng khung `overflow-y-auto` (header
đứng yên, chỉ feed cuộn), và `IntersectionObserver` đặt `root` = khung đó.
**Bê nguyên pattern** `features/kb/TimelineTab.tsx:44-63` (`useInfiniteQuery` + sentinel +
`rootMargin: "120px"`) — bản 07-20 ghi `root: null`, bỏ.

### 4.2b. Thẻ sự kiện — chỉ thời gian + địa điểm

Nội dung một thẻ, KHÔNG hơn:

- Chấm độ tin cậy + **tiêu đề sự kiện** (`label`), có `time_end` thì thêm `→ {mốc cuối}`.
- **Địa danh dạng chữ** (`locations`, tối đa 3, ngăn bằng `·`).
- **Không có địa điểm → không render gì cả** — KHÔNG chữ thay thế kiểu "chưa rõ nơi".
  45% sự kiện có mốc không kèm địa danh, in placeholder cho ngần ấy thẻ là rác thị giác.
- Click thẻ → trải `summary`. **Không có nút "Xem nguồn", không hiện `chunk_id`** — trang
  này để đọc dòng chảy lịch sử, không phải để soi provenance (đã có KB Inspector bên admin
  và danh sách nguồn bên trang hỏi đáp).

Mốc thời gian in **một lần ở chấm trên trục**, không lặp lại trong từng thẻ.

### 4.3. Bộ lọc thời kỳ — TẠM BỎ (chốt 2026-09-01)

**Bản đầu KHÔNG có bộ lọc.** Trang chỉ là một dòng chảy liên tục từ đầu tới cuối, cuộn là
đọc. Nhãn thời kỳ vẫn hiện trên mỗi mốc (badge, §2) — chỉ không bấm lọc được.

Lý do gác lại: 11 nhãn `h1` từ sách quá dài để làm chip nguyên văn, mà ba cách bày (chip
rút gọn tên · dropdown giữ nhãn gốc · gom ~4 giai đoạn tự đặt) đều kéo theo một quyết định
đặt tên/gom nhóm không có sẵn trong dữ liệu. Chưa cần thiết cho bản đầu.

Khi nào muốn thêm lại: dựng `EraFilter.tsx`, thêm tham số `era` cho
`list_timeline_cards()` + `GET /api/timeline/events`, và một endpoint đếm
`GET /api/timeline/eras` để khỏi hardcode danh sách nhãn. Phần join lấy badge (§3.2) đã
sẵn, không phải làm lại.

### 4.4. `timeFormat.ts` — tách ra VÀ sửa lỗi

`shortTime()` / `rangeLabel()` / `parseYearFrac()` đang là hàm private trong
`features/timeline/TimelineBar.tsx:21-49`. **Tách ra `features/timeline/timeFormat.ts`** rồi
cả `TimelineBar` lẫn `TimelineCard` cùng import — tránh nhân bản logic parse.

Đồng thời sửa lỗi đang có thật trên thanh timeline hỏi đáp: `parseYearFrac` khớp
`^(\d{3,4})` nên **năm 2 chữ số (15 mốc) và thế kỷ La Mã (55 mốc) bị loại khỏi thanh không
báo gì, còn 18 mốc TCN bị đặt nhầm thành năm SCN** (`179 TCN` → năm 179). Bản mới:

- `parseYearFrac`: nhận năm 1–4 chữ số · hậu tố ` TCN` → số âm · số La Mã → đầu thế kỷ ·
  không parse được → `null` (cùng quy ước khoá §3.1, để FE và SQL không lệch nhau).
- `shortTime`: `179 TCN` → `179 TCN`; `XII` → `thế kỷ XII`; `40` → `40`; ngày/tháng giữ như cũ.
- Thêm `durationLabel(start, end)` (chỉ dùng khi có `time_end`).
- Test bảng giá trị: `1954-05-07` · `1856-09` · `1945` · `40` · `XII` · `179 TCN` ·
  `III TCN` · `9 tháng`.

`ConfidenceBadge` + `Spinner` + `EmptyState` dùng lại nguyên (`SourceModal` KHÔNG dùng —
xem §4.2b).

### 4.5. Mốc có nhiều sự kiện

Dữ liệu dồn cục nặng: **68% mốc chỉ có 1 sự kiện, nhưng 62% sự kiện lại nằm ở mốc dùng
chung** (1.788 mốc / 3.176 sự kiện). Đông nhất: `1914` (29 sự kiện), `1917` (18),
`1928`/`1930` (16). Mốc càng thô (chỉ có năm) càng dồn; mốc tới ngày hầu như duy nhất.

Cách bày:

- **1 mốc = 1 chấm trên trục**, nhãn thời gian in một lần ở chấm.
- ≤3 sự kiện: hiện hết, cả cụm nằm cùng một bên (so le vẫn tính theo mốc).
- ≥4 sự kiện: hiện 3 thẻ đầu **theo thứ tự đọc của sách** (§3.2) + nút
  "còn N sự kiện ▾" mở tại chỗ, không điều hướng đi đâu.

**KHÔNG gom nhóm theo `parent_event`, không có tiêu đề chủ đề trên mốc** (đã dựng mockup
thử phương án chủ-đề-làm-cấp-trên rồi bỏ, 2026-09-01). Trang này là **biên niên thuần**:
chỉ thời gian → sự kiện → địa điểm.

## 5. Quyết định thiết kế & giới hạn (đã cân nhắc, ghi để khỏi bàn lại)

- **Thẻ = sự kiện lẻ (3.176), KHÔNG phải mục lớn**. Chọn vậy để "cuộn xuống nạp thêm" có ý
  nghĩa thật. Phương án gom thẻ theo mục h2 (36 mục) giống ảnh tham chiếu hơn nhưng cuộn
  vài vòng là hết, không cần scroll vô hạn.
- **Dòng meta co giãn theo dữ liệu, KHÔNG chế độ dài giả**: chỉ 12% event có `time_end`.
  Có `time_end` → `1946 – 1954 · 8 năm`; không có → `07/05/1954`. Ảnh tham chiếu bày
  *triều đại* (đơn vị trăm năm) nên thẻ nào cũng có khoảng + độ dài; dữ liệu ở đây phần lớn
  là *sự kiện điểm*, ép lấp đầy sẽ thành bịa. Đúng tinh thần honest fallback của dự án.
- **Hiện mốc đúng độ mịn nguồn**: `XII` hiện là "thế kỷ XII", KHÔNG quy thành năm đại diện
  (khoá sort 1101 chỉ dùng để xếp chỗ). Đúng tinh thần commit fd1cb70.
- **Biên niên thuần — không dùng `parent_event` ở giao diện**: không làm tiêu đề nhóm, không
  làm cấp trên của mốc. Trang chỉ có thời gian → sự kiện → địa điểm.
- **Thiếu địa điểm thì để trống**, không in chữ thay thế (45% sự kiện có mốc không kèm địa
  danh — placeholder sẽ chiếm gần nửa số thẻ mà chẳng nói thêm điều gì).
- **624 event không có thời gian + mốc rác sẽ vắng mặt** — ghi rõ ở chân trang ("Chỉ hiện
  sự kiện đã xác định được thời gian"), không im lặng bỏ.
- **Chưa gắn bản đồ**: `gazetteer` đang tạm hoãn nên địa danh chỉ hiện dạng **chữ**. Khi nào
  điền xong toạ độ thì thêm map mini vào thẻ — không phải sửa lại cấu trúc.
- **Không dùng trục tỉ lệ theo năm** ở trang này (đã có ở `TimelineBar` bên hỏi đáp). Feed
  cuộn đều thì thế kỷ XX dài 1.617 thẻ là *đúng* — người đọc cảm được giai đoạn nào dồn dập.

## 6. Thứ tự làm

0. **Dựng lại hạ tầng đọc được**: docker up + xác nhận `rag_chunks` (1.212 chunk bộ mới) và
   `timeline_events` đã nạp — mọi số ở §2 đang đo từ artifact, chưa từ DB.
1. Khoá sắp xếp theo phương án đã chốt (§3.1). Phương án A thì kèm
   `run_timeline_index.py --limit -1` để nạp lại bảng (không tốn LLM).
2. `models/timeline.py` + `schemas/timeline.py` + `api/timeline.py` + đăng ký router.
3. Test backend: list, phân trang, event không có `time_end`, mốc TCN/thế kỷ xếp
   đúng chỗ, mốc rác bị loại, bảng thiếu → `([], 0)`.
4. Tách + sửa `timeFormat.ts` (§4.4), giữ test `TimelineBar` hiện có xanh.
5. `TimelineCard` + `TimelineSpine` + route + nav.
6. Test frontend: bố cục so le, nạp trang kế trong khung cuộn riêng, dòng meta 2 dạng,
   nhãn mốc TCN/thế kỷ, feed rỗng.
