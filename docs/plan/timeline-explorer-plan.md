# Plan: Trang "Dòng thời gian" (Timeline Explorer)

**Trạng thái**: chưa code. Chốt thiết kế 2026-07-20.

Trang **độc lập, KHÔNG liên quan hỏi đáp** — không gọi agent-service, không tốn LLM call
nào, không đụng orchestrator. Chỉ đọc `timeline_events` + `rag_chunks` đã index sẵn.

## 1. Mục tiêu

Cho người dùng một cái nhìn trực quan, liên tục về dòng chảy lịch sử từ thời Pháp thuộc đến
sau thống nhất — bày **timeline so le hai bên một trục dọc**, cuộn xuống thì nạp thêm mốc.
Đây là chỗ DUY NHẤT phía user chạm được tới chiều rộng của kho tri thức (hiện 2.984 sự kiện
có thời gian chỉ hiện ra nhỏ giọt ~5-10 cái mỗi câu trả lời, hoặc phải là admin mới xem được
qua KB Inspector).

Tham chiếu hình thức: timeline so le của các trang sử phổ thông (thẻ trái/phải xen kẽ, trục
dọc ở giữa, mỗi thẻ có nhãn thời kỳ). **Không** bê nguyên: xem mục 5.

## 2. Dữ liệu — đã đo thật (2026-07-20)

| Chỉ số | Giá trị |
|---|---|
| `timeline_events` tổng | 3.674 |
| Có `time_start` | **2.984** (690 event không có thời gian → KHÔNG lên trang này) |
| Có `time_end` | **356** (12%) |
| Độ mịn `time_start` | 2.142 tới ngày · 455 tới tháng · 387 chỉ năm |
| Số năm phân biệt | 102 |
| `confidence` | cao 2.568 · vừa 1.099 · thấp 7 |

**Mật độ rất lệch**: 1954 có 356 event, 1972 có 269, 1975 có 268; top 5 năm chiếm 41%.
Chấp nhận được vì đây là feed cuộn vô hạn theo thứ tự thời gian, không phải trục tỉ lệ.

**Nhãn thời kỳ (badge) lấy từ `rag_chunks.heading_path[1]`** — cột `TEXT[]`, phần tử đầu là
chương của tài liệu. Nối qua `source_chunk_ids`, đã verify chạy sạch, không sót event nào:

| Chương | Số event có time |
|---|---|
| Thời kì thuộc địa | 373 |
| Nhật thuộc | 150 |
| Thời kỳ cộng hoà | 2.461 |
| **Tổng** | **2.984** ✓ |

## 3. Backend

Route mới, **chỉ cần đăng nhập** (không gác admin) — cùng lý do với
`GET /api/chat/sources/{chunk_id}`: corpus là SGK, không mật.

### `models/timeline.py` (mới)

```
list_timeline_cards(era: str | None, limit: int, offset: int) -> (rows, total)
```

- `WHERE time_start IS NOT NULL` (loại 690 event vô thời gian).
- `ORDER BY time_start ASC, label ASC` — `time_start` là TEXT nhưng dạng ISO prefix nên
  sort chuỗi ĐÚNG thứ tự thời gian (`"1953-12-01" < "1954" < "1954-01-01"`). Không cần cast.
- Era: `LEFT JOIN LATERAL` lấy `heading_path[1]` của chunk ĐẦU TIÊN trong
  `source_chunk_ids` (1 event hầu như nằm gọn trong 1 mục). `LEFT` để event có chunk lạ vẫn
  ra, badge rỗng — không nuốt mất dòng.
- Bắt `UndefinedTable` → trả `([], 0)` theo pattern `cost.py`.

### `api/timeline.py` (mới)

- `GET /api/timeline/events?era=&limit=30&offset=0` → `{items, total, limit, offset}`,
  khớp hình dạng `listEvents` hiện có để tái dùng `getNextPageParam`.
- Item gồm: `event_id, label, summary, time_start, time_end, locations, confidence, era,
  source_chunk_ids`.
- **Trả luôn `summary` + `source_chunk_ids` trong danh sách** (30 item/trang, không đáng kể)
  → click thẻ mở chi tiết inline mà KHÔNG cần endpoint detail riêng, và nút "Xem nguồn" cắm
  thẳng vào `GET /api/chat/sources/{chunk_id}` đã có.
- Đăng ký router trong `main.py`; schema `schemas/timeline.py`.

## 4. Frontend

- Route `/timeline` (`routes.tsx`, con của `AppShell`, ngang hàng `index: AskPage`).
- Thêm mục nav thứ hai cho user trong `AppSidebar` (hiện khu user chỉ có đúng 1 route).
- `api/timeline.ts` — `listTimelineCards`.
- `pages/TimelinePage.tsx` — wrapper mỏng + `PageHeader`.
- `features/explore/`:
  - `TimelineSpine.tsx` — trục dọc + map thẻ so le (`index % 2`), sentinel
    `IntersectionObserver` ở cuối. **Bê nguyên pattern** `features/kb/TimelineTab.tsx:44-63`
    (`useInfiniteQuery` + sentinel + `rootMargin: "120px"`), khác một chỗ: cuộn theo cả
    trang chứ không trong khung `max-h-[70vh]` → `root: null`.
  - `TimelineCard.tsx` — thẻ: chấm confidence, tiêu đề, dòng meta thời gian, badge era,
    địa danh dạng chữ. Click → trải summary + nút xem nguồn.
  - `EraFilter.tsx` — lọc theo 3 chương (chip), reset về đầu feed.
- Mobile (`< md`): trục dạt sang trái, mọi thẻ nằm bên phải (bố cục so le vỡ ở màn hẹp).

### Tái dùng, không viết lại

`shortTime()` / `rangeLabel()` / `parseYearFrac()` đang là hàm private trong
`features/timeline/TimelineBar.tsx:21-49`. **Tách ra `features/timeline/timeFormat.ts`** rồi
cả `TimelineBar` lẫn `TimelineCard` cùng import — tránh nhân bản logic parse `"YYYY-MM-DD"`.
Thêm `durationLabel(start, end)` ở đó (chỉ dùng khi có `time_end`).

`SourceModal` + `ConfidenceBadge` + `Spinner` + `EmptyState` dùng lại nguyên.

## 5. Quyết định thiết kế & giới hạn (đã cân nhắc, ghi để khỏi bàn lại)

- **Thẻ = sự kiện lẻ (2.984), KHÔNG phải mục lớn (33 h2)**. Chọn vậy để "cuộn xuống nạp
  thêm" có ý nghĩa thật. Phương án 33 thẻ theo mục h2 giống ảnh tham chiếu hơn nhưng cuộn
  vài vòng là hết, không cần scroll vô hạn.
- **Dòng meta co giãn theo dữ liệu, KHÔNG chế độ dài giả**: chỉ 12% event có `time_end`.
  Có `time_end` → `1946 – 1954 · 8 năm`; không có → `07/05/1954`. Ảnh tham chiếu bày
  *triều đại* (đơn vị trăm năm) nên thẻ nào cũng có khoảng + độ dài; dữ liệu ở đây phần lớn
  là *sự kiện điểm*, ép lấp đầy sẽ thành bịa. Đúng tinh thần honest fallback của dự án.
- **690 event không có thời gian sẽ vắng mặt** — ghi rõ ở chân trang ("Chỉ hiện sự kiện đã
  xác định được thời gian"), không im lặng bỏ.
- **Chưa gắn bản đồ**: `gazetteer` đang tạm hoãn nên địa danh chỉ hiện dạng **chữ**. Khi nào
  chạy geocoding thì thêm map mini vào thẻ — không phải sửa lại cấu trúc.
- **Không dùng trục tỉ lệ theo năm** ở trang này (đã có ở `TimelineBar` bên hỏi đáp). Feed
  cuộn đều thì 1954 dài 356 thẻ là *đúng* — người đọc cảm được năm nào dồn dập.

## 6. Thứ tự làm

1. `models/timeline.py` + `schemas/timeline.py` + `api/timeline.py` + đăng ký router.
2. Test backend: list, phân trang, lọc era, event không có `time_end`, bảng thiếu.
3. Tách `timeFormat.ts` khỏi `TimelineBar` (giữ test hiện có xanh).
4. `TimelineCard` + `TimelineSpine` + route + nav.
5. Test frontend: bố cục so le, nạp trang kế, dòng meta 2 dạng, feed rỗng.
