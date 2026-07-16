# Plan: Giao diện map-first — map nền toàn màn hình + chat nổi (trang hỏi đáp)

> Trạng thái: **ĐÃ CODE XONG cả 4 phase (2026-07-14)** — verify bằng browser thật
> (Puppeteer headed): 18/18 check với marker giả + 7/7 check với dữ liệu thật (câu hỏi
> end-to-end qua SSE). Test: FE 44/44, agent-service 212/212.
> Phạm vi: CHỈ trang hỏi đáp user (`/` — `AskPage`). Admin không đổi.
>
> **2 bug THẬT phát hiện khi verify (đã sửa, không nằm trong plan gốc):**
> 1. `gazetteer_store.py::lookup_coords` query bảng `gazetteer` **chưa tồn tại** (khâu
>    geocoding đang hoãn → chưa chạy `build_gazetteer.py` lần nào) → `UndefinedTable` ném
>    ngược lên, giết CẢ `build_visualization` → answer trả về `Visualization lỗi:
>    UndefinedTable`, timeline KHÔNG BAO GIỜ hiện dù `timeline_events` có 3.674 dòng thật.
>    CLAUDE.md vốn hứa "gazetteer rỗng → fallback chỉ-timeline, không vỡ" — nhưng code chỉ
>    đúng khi bảng RỖNG, không đúng khi bảng CHƯA CÓ. Sửa: bắt `UndefinedTable` → `{}`
>    (đúng pattern `cost.py`/`document.py` sẵn có trong repo).
> 2. `vizPanelOpen` chỉ được bật trong `useChat` khi có event SSE `visualization` → **mở
>    lại phiên cũ từ DB thì bản đồ không hiện** ở layout split (dữ liệu có sẵn trong
>    `messages.visualization` nhưng cờ vẫn false). Sửa: bỏ `openViz` khỏi `useChat`, cho
>    `AskPage` mở panel theo DỮ LIỆU (`useEffect` trên `activeViz`) — áp dụng cho cả viz
>    từ SSE lẫn viz nạp lại từ DB.

## 1. Yêu cầu (chốt với user 2026-07-14)

1. **Map làm nền**: bản đồ nằm sẵn dưới, full màn hình vùng nội dung; khu hỏi đáp là
   card **nổi** trên map.
2. **Toggle 2 chế độ**: ấn nút chuyển giữa `float` (chat nổi trên map — mặc định) và
   `split` (map 1 bên, chat 1 bên — chính là layout hiện tại).
3. **Bỏ hết line đường đi** trên map — marker sự kiện lịch sử không cần đường xá hiện đại.
4. **Mở trang là thấy Việt Nam** — khung nhìn MẶC ĐỊNH ghim ở VN (làm rõ 2026-07-14:
   chỉ là initial view, KHÔNG khoá — user muốn kéo hay zoom in/out đi đâu thì tuỳ).
5. **Trình chiếu sự kiện** (thêm 2026-07-14): nút ▶ để hệ thống tự "kể" các sự kiện
   của câu trả lời theo thứ tự thời gian — highlight lần lượt từng sự kiện, map pan
   tới marker (nếu có toạ độ), dừng ~2s rồi sang sự kiện kế. Tương lai tích hợp
   text-to-speech: chiếu đến đâu đọc đến đó (CHƯA làm, chỉ chừa móc).

## 2. Quyết định kỹ thuật (đã tra docs Google Maps 2026-07-14)

### 2.1. Ẩn đường: Cloud-based styling gắn Map ID (chốt với user 2026-07-14)

Xung đột phát hiện khi tra docs:

- Ẩn road bằng **style JSON trong code** (`styles` MapOption) chỉ hoạt động trên
  **raster map KHÔNG có `mapId`** ("A map's styles property can only be set on a raster map").
- `AdvancedMarker` (đang dùng ở `EventMarker.tsx`) **bắt buộc có `mapId`**.
- Map có `mapId` chỉ style được qua **Cloud-based styling trên Google Cloud Console**.

**Chọn: Cloud-based styling** — user TỰ chỉnh style trên Cloud Console (Map Styles) và
gắn vào một **Map ID thật**. Nhờ vậy giữ NGUYÊN `AdvancedMarker`+`Pin` hiện có (API
chính chủ, không deprecated), về sau đổi style trên console không cần sửa code/deploy.
(Phương án code-only — bỏ mapId + legacy `Marker` — đã cân nhắc nhưng BỎ vì dính API
deprecated trong khi user sẵn sàng thao tác console.)

Việc user làm trên console (1 lần):

1. Google Maps Platform → **Map management** → tạo **Map ID** loại JavaScript,
   **chọn VECTOR** (chốt với user 2026-07-14) — cho zoom số lẻ (5.5…) và camera
   animate mượt khi pan + zoom đồng thời (phục vụ trình chiếu, xem mục 3).
2. **Map styles** → tạo style ẨN: `road` (cả geometry lẫn label), `transit`, icon
   `poi`. GIỮ: `administrative` (ranh giới tỉnh/quốc gia — có ích cho ngữ cảnh lịch
   sử), `water`, `landscape`, label tỉnh/thành.
3. Gắn style vào Map ID vừa tạo.
4. Bỏ Map ID vào `apps/frontend/.env`: `VITE_GOOGLE_MAPS_MAP_ID=<id>`
   (+ ghi mẫu vào `.env.example`).

Phía code: `mapId` đang hardcode `"history-vn"` (chuỗi tự đặt, KHÔNG phải ID thật trên
console) → đổi sang đọc `import.meta.env.VITE_GOOGLE_MAPS_MAP_ID`, thiếu env thì
fallback chuỗi cũ — map vẫn chạy với style mặc định (có đường xá), không vỡ.

**Đã verify 2026-07-14** (headless Chrome + Map ID thật `5c04798e…`, 3 marker giả):
đường xá ẩn sạch, `AdvancedMarker`+`Pin` chạy đúng 3 màu confidence, Google xác nhận
Map ID là vector (test fallback raster do headless không GPU — browser thật chạy vector;
style ẩn đường VẪN ăn cả khi fallback → máy yếu WebGL không vỡ).

### 2.1b. `language="vi"` + `region="VN"` — BẮT BUỘC

Mặc định Google render label tiếng Anh: **"Paracel Islands" / "Spratly Islands" /
"South China Sea"**. Không chấp nhận được cho đồ án lịch sử Việt Nam. Thêm 2 prop vào
`<APIProvider>` → "quần đảo Hoàng Sa" / "quần đảo Trường Sa" / "Biển Đông" / "Hà Nội"
(đã verify bằng ảnh chụp). Không đụng Map ID/style.

### 2.1c. Màu: GIỮ map mặc định + GIỮ palette web, chỉ chỉnh pin (chốt 2026-07-14)

Map để nguyên terrain xanh của Google (chỉnh tay dễ ra màu bùn); web giữ nguyên tông
kem + đỏ `#A4161A` (đổi theme = sơn lại cả admin, mà card chat vốn ĐỤC nên kem trên
xanh đọc như tờ giấy đặt trên bàn bản đồ — không chối; đỏ/xanh lá là cặp bù màu, marker
nổi bật nhất có thể).

Vấn đề thật chỉ ở pin `thấp` `#e0a3a4` (hồng nhạt chìm trên nền xanh) → chữa bằng
**viền halo kem** `#fffdf9` (= token `paper-card`) cho cả 3 pin: tách pin khỏi mọi nền,
đồng thời chính là chi tiết buộc map với tông giấy của app. Confidence vẫn phân biệt
bằng độ đậm ruột pin + scale (đúng visualization contract), nâng nhẹ độ bão hoà mức
`thấp` để không chìm. Sửa ~3 dòng `EventMarker.tsx`.

### 2.2. Khung nhìn mặc định: Việt Nam — KHÔNG khoá pan/zoom

Làm rõ với user 2026-07-14: "ghim ở Việt Nam" = **khung nhìn lúc mới vào trang**, không
phải khoá vĩnh viễn. **KHÔNG dùng `restriction`/`minZoom`** — user kéo/zoom tự do.

- `defaultZoom: 6` (Map ID vector → chỉnh được số lẻ 5.5/6.5 nếu 6 bị cụt Bắc/Nam);
  `defaultCenter` hiện `{lat: 16.0, lng: 107.8}`: với card chat nổi
  bên TRÁI, đất liền (lng 102–109.5) sẽ render lệch trái → bị card che. Dời center về
  hướng tây (ước lượng `lng ≈ 104.5`) để đất liền rơi vào phần map lộ ra bên phải —
  **chốt số cuối bằng mắt lúc code**.
- Nhờ không khoá, địa danh nước ngoài trong corpus (Paris, Genève, Réunion, Trung
  Quốc…) VẪN hiện được trên map khi gazetteer chạy sau này — user pan tới là thấy.
- **Khi câu trả lời mới có marker → `fitBounds` về cụm marker** (padding né card chat)
  để user không phải tự đi tìm; không có marker mới → giữ nguyên khung nhìn hiện tại,
  không giật map vô cớ.

### 2.3. Map luôn render làm nền — đảo ngược 1 tối ưu có chủ đích

`EventMap.tsx:18` hiện cố ý KHÔNG nạp script Google Maps khi `markers.length === 0`
(gazetteer hoãn → markers luôn rỗng → map hiện chưa bao giờ render). Map-first đảo
ngược điều này: **luôn render base map khi có API key**, kể cả 0 marker.

- **Chi phí**: mỗi lần mở trang chat = 1 dynamic map load tính phí Google. Free tier
  thừa cho đồ án, nhưng ghi lại vì là trade-off có chủ đích.
- Không có `VITE_GOOGLE_MAPS_API_KEY` → giữ honest fallback: `MapEmptyState` (nền giấy
  + thông báo) làm backdrop, chat vẫn hoạt động bình thường. `MapEmptyState` thu gọn
  còn reason `no-key` (reason `no-markers` hết chỗ dùng — base map trống là trạng thái
  hợp lệ, không phải empty state).

## 3. Thiết kế UX 2 chế độ

### Mode `float` (mặc định)

```
┌─AppSidebar─┬──────────────────────────────────────────────┐
│ (nav dọc,  │  MAP NỀN (absolute inset-0)                  │
│  giữ       │  ┌─Card chat nổi─────────┐        [⇄ toggle] │
│  nguyên)   │  │ [☰ phiên]             │   ·marker         │
│            │  │  bubbles…             │        ·marker    │
│            │  │  citations…           │                   │
│            │  │  Composer             │                   │
│            │  └───────────────────────┘                   │
│            │  ┌─TimelineBar nổi (overlay, rounded)──────┐ │
│            │  └──────────────────────────────────────────┘│
└────────────┴──────────────────────────────────────────────┘
```

- **Card chat**: nổi bên trái, **đục hoàn toàn** (`bg-paper-card` + shadow + rounded —
  KHÔNG translucent, chữ đè map lốm đốm rất mỏi mắt), rộng ~520px, neo top/bottom có lề.
  Chứa nguyên `ChatPanel` hiện có (empty-state câu hỏi mẫu + MessageList + Composer).
- **Sidebar phiên** (`ConversationSidebar`): không còn là cột cứng — thành **drawer**
  trượt từ trái, mở bằng nút ☰ trên card chat, đóng bằng backdrop/✕. Component giữ
  nguyên, chỉ bọc lại.
- **TimelineBar**: nổi ở đáy đè lên map (kiểu Google Earth) — thêm prop
  `variant: "docked" | "overlay"` chỉ đổi class khung ngoài (overlay: `mx-4 mb-4
  rounded-xl border shadow-lg`), toàn bộ logic zoom/pan/cluster giữ nguyên.
- **Marker** cập nhật thẳng trên map nền sau mỗi câu trả lời (`latestVisualization`
  như hiện tại); chưa có viz → map nền trống, timeline ẩn. `VizPanel` không dùng ở
  mode này (không có khái niệm đóng/mở map).
- Chú ý pointer-events: card chat chặn wheel/drag lọt xuống map bên dưới.

### Mode `split`

Giữ NGUYÊN layout hiện tại của `AskPage` (sidebar cột + chat + `VizPanel` mở khi có
viz + TimelineBar docked full-width). `vizPanelOpen`/`closeViz` chỉ còn ý nghĩa ở mode
này. Khác biệt duy nhất sau plan: map trong `VizPanel` giờ luôn render base map
(markers rỗng → map VN trống + header "0 sự kiện" — vẫn honest).

### Toggle

Nút nổi **góc trên-phải vùng nội dung**, hiện ở CẢ 2 mode (float: đè trên map; split:
đè trên mép phải) — 1 chỗ cố định, không phụ thuộc VizPanel có mở hay không. Icon
lucide (`Columns2` ⇄ `Map`), tooltip "Tách đôi màn hình" / "Map toàn nền".

`selectedEventId` (link 2 chiều map ↔ timeline) dùng chung store, hoạt động y hệt ở
cả 2 mode — không đụng.

### Trình chiếu sự kiện (nút ▶ — "tour")

Khả thi RẺ vì hạ tầng link đã có sẵn: `selectedEventId` là nguồn sự thật chung — set
nó là marker tự phóng to (`EventMarker` scale 1.3, có sẵn) VÀ timeline tự mở popover
chi tiết (`TimelineBar` có sẵn). Tour về bản chất = sắp event theo thời gian → mỗi
tick `setSelectedEvent(event_id)` → chờ ~2s → tick tiếp.

- **Thứ tự = thứ tự timeline** (`time_start` tăng dần, tái dùng logic parse
  `parseYearFrac`). Event KHÔNG có marker (chưa geocode — hiện là tất cả) vẫn được
  "chiếu" trên timeline (highlight + popover); map chỉ pan khi có toạ độ → feature
  demo được NGAY từ bây giờ, gazetteer xong thì phần map tự sống dậy.
- **Map pan theo store, KHÔNG theo tour**: `EventMap` thêm effect "`selectedEventId`
  đổi → có marker tương ứng thì `map.panTo` (animate sẵn của Google)". Nhờ vậy (1)
  tour engine không cần chạm map instance (né hạn chế `useMap()` chỉ gọi được bên
  trong `APIProvider` — TimelineBar nằm ngoài), (2) click tay một dòng timeline map
  cũng pan theo — tiện cả UX thường.
- **Camera khi trình chiếu — CÓ zoom vào** (chốt 2026-07-14): store thêm cờ
  `tourPlaying`; effect trên đọc cờ để phân biệt — đang tour → `panTo` +
  `setZoom(TOUR_FOCUS_ZOOM ≈ 9, chốt bằng mắt)` dí vào điểm đang kể (Map ID vector
  nên cặp pan+zoom animate mượt); tour dừng/kết thúc → `fitBounds` trả về toàn cảnh
  các marker của câu trả lời. Click tay NGOÀI tour giữ hành vi hiền: chỉ `panTo`,
  tôn trọng mức zoom user đang đặt.
- **Nút đặt ở header TimelineBar** ("▶ Trình chiếu" ⇄ "⏹ Dừng") — hiện ở cả 2 layout
  mode. Disable khi đang stream câu trả lời.
- **Engine**: hook mới `features/timeline/useEventTour.ts` — `status: idle|playing` +
  index, chuỗi `setTimeout` (`TOUR_STEP_MS ≈ 2000`). Dừng khi: hết danh sách, bấm ⏹,
  items đổi (câu hỏi mới), hoặc user tự click marker/timeline khác giữa chừng (hook
  thấy `selectedEventId` lệch với cái nó vừa set → tương tác tay thắng máy → dừng).
- **Móc cho TTS (CHƯA làm)**: bước "chờ N giây rồi sang tiếp" thiết kế thành
  *advance-trigger* cắm được — mặc định là timer; khi có TTS thì trigger =
  `utterance.onend` (Web Speech API `speechSynthesis` miễn phí nhưng giọng tiếng Việt
  tuỳ OS/browser; muốn giọng tốt dùng Google Cloud TTS — quyết sau). Hook expose
  `currentEvent` (label + summary) để TTS chỉ việc nghe theo, không sửa engine.

## 4. Thay đổi theo file

| File | Việc |
|---|---|
| `features/map/EventMap.tsx` | `mapId` đọc từ env `VITE_GOOGLE_MAPS_MAP_ID` (fallback chuỗi cũ); `APIProvider` thêm `language="vi"` + `region="VN"` (mục 2.1b); bỏ early-return khi 0 marker; chỉnh `defaultCenter`/`defaultZoom`; `fitBounds` khi danh sách marker đổi; `panTo`/zoom marker khi `selectedEventId` đổi; chỉ còn fallback `no-key` |
| `features/timeline/useEventTour.ts` (MỚI) | Engine trình chiếu: sort theo thời gian, chuỗi timer, advance-trigger cắm được (móc TTS), expose `currentEvent`, tự dừng khi user can thiệp/items đổi |
| `features/map/EventMarker.tsx` | Giữ `AdvancedMarker`+`Pin` (ẩn đường do style Map ID lo); chỉ đổi bảng màu: viền halo kem `#fffdf9` cả 3 mức + nâng bão hoà mức `thấp` (mục 2.1c) |
| `apps/frontend/.env` + `.env.example` | Thêm `VITE_GOOGLE_MAPS_MAP_ID` |
| `features/map/MapEmptyState.tsx` | Thu gọn còn reason `no-key` |
| `store/chatUiStore.ts` | Thêm `layoutMode: "float" \| "split"` (mặc định `float`) + `setLayoutMode` + `convDrawerOpen` + `tourPlaying` (cờ cho EventMap đổi hành vi camera, không persist); persist CHỈ `layoutMode` (zustand `persist` + `partialize` — store còn lại vẫn ephemeral); `reset()` không đụng `layoutMode` |
| `pages/AskPage.tsx` | Rẽ nhánh theo `layoutMode`: float = container relative + map absolute + card chat + drawer + TimelineBar overlay + toggle; split = giữ nguyên JSX hiện có |
| `features/chat/VizPanel.tsx` | Giữ nguyên (chỉ dùng ở split) |
| `features/timeline/TimelineBar.tsx` | Thêm prop `variant`, đổi class khung ngoài; nút ▶ Trình chiếu / ⏹ Dừng ở header (gọi `useEventTour`) |
| `features/chat/ConversationSidebar.tsx` | Giữ nguyên; AskPage bọc drawer ở float mode (absolute + transition tay, không cần Radix — Modal hiện có là dialog giữa màn hình, không hợp drawer trượt) |

Không đụng: `useChat`/`chatReducer`/SSE, `Composer` (chọn mode per câu hỏi giữ nguyên),
citation viewer, backend/agent-service.

## 5. Thứ tự làm + verify

0. **Việc user làm trước (console, 1 lần)**: tạo Map ID + style ẩn đường + gắn style
   (các bước ở mục 2.1), đưa `VITE_GOOGLE_MAPS_MAP_ID` vào `apps/frontend/.env`.
1. **Phase 1 — Map core**: `EventMap` + `MapEmptyState`.
   Verify: dev server, tạm hardcode vài marker giả (Hà Nội/Huế/Sài Gòn, đủ 3 mức
   confidence) để nhìn bằng mắt — hết đường xá/POI (style ăn theo Map ID), mở trang
   thấy ngay VN, pan/zoom tự do, fitBounds về marker giả, pin đúng màu, click chọn
   phóng to. **XOÁ mock trước khi commit.**
2. **Phase 2 — Layout float + toggle**: `chatUiStore` + `AskPage` + drawer + TimelineBar
   overlay + nút toggle. Verify: hỏi thật end-to-end (câu có timeline data), toggle
   qua lại 2 mode giữa chừng stream, reload giữ mode (persist), drawer đổi phiên,
   link timeline ↔ map qua `selectedEventId`.
3. **Phase 3 — Trình chiếu**: `useEventTour` + nút ▶/⏹ ở TimelineBar + panTo-theo-store
   ở EventMap. Verify: câu hỏi ra ≥3 sự kiện timeline → bấm ▶: highlight chạy lần
   lượt đúng thứ tự thời gian, popover mở theo, click tay giữa chừng thì tour dừng,
   gửi câu hỏi mới thì tour dừng.
4. **Phase 4 — Chốt**: `npm run typecheck` + `npm run test` (suite hiện có; store/logic
   mới thuần UI — không thêm test nặng; riêng `useEventTour` logic thuần đáng 1 file
   test nhỏ), rà pointer-events + responsive tối thiểu, cập nhật `CLAUDE.md`:
   - dòng "Render map = … (AdvancedMarkerElement)": bổ sung style quản lý bằng
     Cloud-based styling gắn Map ID (`VITE_GOOGLE_MAPS_MAP_ID`), KHÔNG style JSON
     trong code;
   - mô tả layout AskPage (2 mode) ở mục Frontend layout;
   - thêm file plan này vào danh sách `docs/plan/`.

## 6. Kết quả thực tế sau khi code (2026-07-14)

Số đo lấy từ browser thật (đọc thẳng `map.getZoom()`/`getCenter()`), không phải suy đoán:

- Vào trang: `fitBounds` về cụm marker (zoom 6). Bấm ▶ → camera dí vào đúng toạ độ sự
  kiện đang kể (Gia Định `10.78,106.70`, zoom 9) → kể xong tự lùi về toàn cảnh (zoom 6.34).
- Tour: chạy đúng thứ tự thời gian, popover timeline mở theo; Escape/click tay giữa chừng
  → dừng (tay thắng máy); câu hỏi mới → dừng; chạy hết → tự dừng + bỏ chọn.
- Câu hỏi thật (`Diễn biến chính của chiến dịch Điện Biên Phủ 1954?`): 17–19s, ra **129 mốc
  timeline** (sau khi sửa bug gazetteer), citations gộp theo mục vẫn nguyên vẹn.
- Click chuột thật lên vùng nằm trên map: **14/14 ăn** (đo riêng để loại nghi ngờ iframe của
  Google Maps nuốt click — chỉ là artifact của Puppeteer lúc trang chưa ổn định).
- **⚠️ Việc còn lại của user (Cloud Console)**: ở zoom sâu (~9, tức lúc trình chiếu dí vào
  điểm) **đường xá hiện trở lại** (thấy QL12/QL32/AH13). Style hiện chỉ ẩn road ở zoom thấp
  → cần chỉnh lại trên Cloud Console cho `road` (+ các nhánh highway/arterial/local, cả
  geometry lẫn labels/icons) là **Hidden ở mọi zoom**, không phải "Simplified".

## 7. Rủi ro / ghi chú

- **Billing**: map load mỗi lần mở trang chat (mục 2.3). Free tier đủ; nếu lo, có thể
  lazy-load map sau first paint — KHÔNG làm vội.
- **Style sống NGOÀI repo**: gắn với Google Cloud project của user — demo bằng
  account/project khác phải tạo lại Map ID + style theo các bước mục 2.1. Thiếu env →
  map vẫn chạy style mặc định (có đường xá), không vỡ.
- **Map nền hiện tại chỉ mang tính thẩm mỹ**: gazetteer đang hoãn → 0 marker thật.
  Layout làm trước, khi `build_gazetteer.py` chạy (hạng mục CUỐI) marker tự xuất hiện,
  không phí công.
