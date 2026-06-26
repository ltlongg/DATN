# Google Maps API — Reference (geocoding + map render)

> Tài liệu tổng hợp Google Maps Platform dùng trong dự án, để khỏi tra lại docs mỗi
> lần. Nguồn chính thức ở cuối file. Trong repo, Google **thay Mapbox** ở khâu geocode
> địa danh (`apps/agent-service/app/indexing/geocoding/geocoder.py`) và render bản đồ
> POC (`google_map_test.py`, `scripts/show_google_map.py`).
>
> Key dùng ở `.env`: `GOOGLE_MAPS_API_KEY`. Bật các API sau trong Google Cloud Console
> cho key này: **Geocoding API** (REST, server-side) và **Maps JavaScript API**
> (render bản đồ ở browser).

---

## 1. Geocoding API (forward) — REST, dùng server-side

Đổi địa chỉ/tên địa danh → toạ độ (lat/lng). Đây là phần CỐT LÕI dự án dùng để dựng
`gazetteer` (địa danh → toạ độ) offline.

### Endpoint

```
https://maps.googleapis.com/maps/api/geocode/json?parameters
```

- `json` (khuyến nghị) hoặc `xml`. **Bắt buộc HTTPS.**
- Method: `GET`.

### Tham số

| Tham số | Bắt buộc | Ý nghĩa |
|---|---|---|
| `key` | ✅ | API key (quota/billing). |
| `address` | ✅ (hoặc `components`) | Địa chỉ/tên cần geocode. KHÔNG nhận lat/lng. URL-encode (httpx tự lo). |
| `components` | tuỳ chọn | Bộ lọc, các phần tử ngăn bằng `\|`, mỗi phần tử dạng `component:value`. |
| `bounds` | tuỳ chọn | Bias theo viewport: `sw_lat,sw_lng\|ne_lat,ne_lng`. Chỉ **bias**, không ép. |
| `region` | tuỳ chọn | ccTLD 2 ký tự (vd `vn`), bias theo quốc gia. |
| `language` | tuỳ chọn | Ngôn ngữ kết quả (vd `vi` → tên + `formatted_address` có dấu tiếng Việt). |

### `components` — phần tử & mức "ép" vs "bias"

| Component | Hành vi |
|---|---|
| `country` | **Bộ lọc ÉP** — khớp tên nước hoặc mã ISO 3166-1 alpha-2. `country:VN` = chỉ trả kết quả trong Việt Nam. |
| `postal_code` | Bộ lọc ÉP (mã/tiền tố mã bưu chính). |
| `route` | Chỉ **bias** (không ép). |
| `locality` | Chỉ **bias**. |
| `administrative_area` | Chỉ **bias**. |

→ **Dự án KHÔNG dùng `components=country:VN`** (không ép chỉ-Việt-Nam): corpus lịch sử
VN có nhiều địa danh ở nước ngoài (Paris/Versailles ký hiệp ước, Genève 1954, Trung Quốc,
đảo Rêuyniông nơi lưu đày...) cần geocode đúng. Chỉ dùng `region=vn` (BIAS — ưu tiên địa
danh VN khi trùng tên, KHÔNG lọc) + `language=vi`. (`components=country:VN` vẫn là lựa
chọn nếu sau này cần khoá cứng trong VN.)

### Cấu trúc JSON trả về

```jsonc
{
  "status": "OK",
  "results": [
    {
      "formatted_address": "Gò Công, Tiền Giang, Việt Nam",
      "geometry": {
        "location":      { "lat": 10.3539, "lng": 106.6678 },   // ← lat/lng tách rõ, KHÔNG phải [lon,lat]
        "location_type": "APPROXIMATE",
        "viewport":      { "northeast": {...}, "southwest": {...} },
        "bounds":        { "northeast": {...}, "southwest": {...} }
      },
      "address_components": [ { "long_name": "...", "short_name": "...", "types": ["..."] } ],
      "types":         ["locality", "political"],
      "place_id":      "ChIJ...",       // ← lưu vô thời hạn được (xem §4 ToS)
      "partial_match": false             // true = Google không khớp chính xác chuỗi truy vấn
    }
  ],
  "error_message": "..."   // chỉ có khi status != OK
}
```

> **Khác Mapbox v6:** Mapbox trả `geometry.coordinates = [lon, lat]` (đảo thứ tự) còn
> Google trả `geometry.location.{lat, lng}` tách rõ → không còn bẫy đảo lon/lat.

### `geometry.location_type`

- `ROOFTOP` — chính xác tới số nhà.
- `RANGE_INTERPOLATED` — nội suy giữa 2 điểm trên đường.
- `GEOMETRIC_CENTER` — tâm hình (đường/đa giác).
- `APPROXIMATE` — gần đúng (tỉnh/huyện/vùng thường rơi vào đây).

### `types` (mảng phân loại — dùng suy confidence)

| type | Ý nghĩa | Map sang confidence (dự án) |
|---|---|---|
| `country` | Quốc gia (cấp cao nhất) | **thấp** (không định vị được nơi cụ thể) |
| `administrative_area_level_1` | Cấp 1 dưới quốc gia = **tỉnh/thành** (ở Mỹ là bang) | **vừa** (khá thô) |
| `administrative_area_level_2` | Cấp 2 = **quận/huyện** | cao |
| `administrative_area_level_3..7` | Đơn vị hành chính nhỏ hơn | cao |
| `locality` | Thành phố/thị xã | cao |
| `sublocality` | Dưới locality (phường...) | cao |
| `neighborhood` | Khu phố có tên | cao |
| `route` | Tuyến đường | cao |
| `street_address` | Địa chỉ đường chính xác | cao |
| `point_of_interest` | Địa điểm nổi bật | cao |
| `premise` | Toà nhà/cụm nhà có tên | cao |
| `natural_feature` | Đặc điểm tự nhiên (sông/núi) | cao |
| `political` | Thực thể chính trị (thường kèm type khác) | — (không quyết định một mình) |

Logic dự án (`_confidence_from_types`): `country` → `thấp`; nếu có
`administrative_area_level_1` → `vừa`; còn lại → `cao`. (Mirror logic cũ theo
`feature_type` của Mapbox.)

### Status codes

| status | Ý nghĩa | Xử lý trong geocoder |
|---|---|---|
| `OK` | Có ≥1 kết quả. | Parse `results[0]`. |
| `ZERO_RESULTS` | Không tìm thấy (địa danh không tồn tại / đã đổi tên). | Trả `None` → LLM fallback. |
| `OVER_DAILY_LIMIT` | Thiếu/sai key, billing tắt, vượt cap, payment lỗi. | Log + `None` → LLM. |
| `OVER_QUERY_LIMIT` | Vượt quota (QPS). | Log + `None` → LLM. |
| `REQUEST_DENIED` | Request bị từ chối (key sai/chưa bật API/IP restriction). | Log + `None` → LLM. |
| `INVALID_REQUEST` | Thiếu `address`/`components`. | Log + `None`. |
| `UNKNOWN_ERROR` | Lỗi server, thử lại có thể được. | Log + `None`. |

> ⚠️ Google trả **HTTP 200** kèm `status` lỗi trong body (vd `REQUEST_DENIED`) — phải
> kiểm tra `body["status"] == "OK"`, KHÔNG chỉ dựa `raise_for_status()`.

### Ví dụ request

```
# Cơ bản
https://maps.googleapis.com/maps/api/geocode/json?address=1600+Amphitheatre+Parkway&key=KEY

# Bias VN + tiếng Việt (dự án dùng kiểu này — KHÔNG ép, để geocode được cả nước ngoài)
https://maps.googleapis.com/maps/api/geocode/json?address=Gò+Công&language=vi&region=vn&key=KEY
```

---

## 2. Maps JavaScript API — render bản đồ ở browser

Dùng cho POC `google_map_test.py` và `scripts/show_google_map.py`, sau này cho
`features/map` của frontend.

### Bootstrap loader (Dynamic Library Import — khuyến nghị)

Inline script loader chính thức (đã dùng trong `google_map_test.py`):

```js
(g => { /* ... loader rút gọn của Google ... */ })({
  key: "API_KEY",
  v: "weekly",       // hoặc "quarterly" cho ổn định
  region: "VN",
  language: "vi",
});
```

Sau đó nạp từng thư viện theo nhu cầu:

```js
const { Map }                  = await google.maps.importLibrary("maps");
const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");
```

`window.gm_authFailure` được gọi khi key bị từ chối → hiển thị thông báo lỗi rõ ràng.

### Tạo bản đồ

```js
const map = new Map(document.getElementById("map"), {
  center: { lat: 21.0285, lng: 105.8542 },   // Hà Nội
  zoom: 13,
  mapId: "DEMO_MAP_ID",   // BẮT BUỘC nếu dùng AdvancedMarkerElement
});
```

### Marker — dùng `AdvancedMarkerElement` (cách mới)

```js
const { AdvancedMarkerElement } = await google.maps.importLibrary("marker");
const marker = new AdvancedMarkerElement({
  map,
  position: { lat: 10.3539, lng: 106.6678 },
  title: "Gò Công",
});
```

- **Map ID bắt buộc**: AdvancedMarkerElement KHÔNG load nếu thiếu `mapId`. Dùng
  `"DEMO_MAP_ID"` để test nhanh, hoặc tạo Map ID riêng trong Cloud Console (Map
  Management) cho production.
- `google.maps.Marker` cổ điển vẫn chạy (không cần mapId) nhưng là legacy — ưu tiên
  AdvancedMarkerElement cho code mới.

### InfoWindow (popup)

```js
const { InfoWindow } = await google.maps.importLibrary("maps");
const info = new InfoWindow({ content: "Gò Công, Tiền Giang" });
marker.addListener("gmp-click", () => info.open({ map, anchor: marker }));
info.open({ map, anchor: marker });   // mở sẵn
```

### Vector map + Data-Driven Styling (ranh giới hành chính)

Với Map ID bật **Vector rendering**, có thể tô ranh giới hành chính:

```js
const layer = map.getFeatureLayer("ADMINISTRATIVE_AREA_LEVEL_1"); // tỉnh/thành
layer.style = { strokeColor: "#E74C3C", strokeWeight: 2, fillColor: "#E74C3C", fillOpacity: 0.05 };
```

(Xem `google_map_test.py` — đã có sẵn demo tô `ADMINISTRATIVE_AREA_LEVEL_1/2`.)

---

## 3. Cách dự án dùng (mapping code)

| Khâu | File | Ghi chú |
|---|---|---|
| Geocode địa danh (Google → LLM fallback) | `app/indexing/geocoding/geocoder.py` | `_google_geocode()` gọi REST; name-gate loại fuzzy-match; `region=vn` bias, KHÔNG lọc bbox (địa danh nước ngoài vẫn nhận). |
| Cấu hình key | `app/core/config.py` | `google_maps_api_key` (đọc `GOOGLE_MAPS_API_KEY`). Rỗng → bỏ Google, chỉ LLM. |
| Build bảng toạ độ | `scripts/build_gazetteer.py` | Geocode hàng loạt, cache `dataset/gazetteer.json`, upsert `gazetteer`. |
| Smoke test geocode | `scripts/test_google_geocoding.py` | In toạ độ cho 1 truy vấn. |
| Render địa điểm | `scripts/show_google_map.py`, `google_map_test.py` | Maps JS API + AdvancedMarkerElement. |

**Suy confidence** (`_confidence_from_types`): `country` → `thấp`,
`administrative_area_level_1` → `vừa`, còn lại → `cao`.

**Name-gate** (`_name_matches`): mọi token tên truy vấn (bỏ dấu + `y→i` + `đ→d`) phải
nằm trong `formatted_address`, nếu không coi như Google không tìm thấy → LLM lo (vì
Google hay trả "đại khái" 1 kết quả gần đúng, cờ `partial_match=true`).

> ⚠️ **Caveat địa danh nước ngoài + `language=vi`**: Google ĐỊA PHƯƠNG HOÁ tên nước
> ngoài sang tiếng Việt (vd `Paris` → `"Pa ri, Pháp"`, `London` → `"Luân Đôn"`). Nếu
> surface form trong corpus là tên gốc ("Paris") mà Google trả "Pa ri" → name-gate
> **không khớp** → rơi xuống LLM (LLM biết Paris = Pa-ri = Ba Lê, vẫn ra đúng toạ độ).
> Địa danh nước ngoài mà tên Việt giữ nguyên token (Genève→"Genève, Thụy Sĩ", Quảng
> Châu→"Quảng Châu, Trung Quốc") thì Google khớp thẳng. → Hành vi đúng & honest, chỉ là
> một số tên Tây resolve qua LLM thay vì Google. `region=vn` KHÔNG ảnh hưởng việc này
> (đã đo: Paris ra "Pa ri" dù có/không `region`).

---

## 4. ⚠️ Terms of Service — caching (QUAN TRỌNG)

Google Maps Platform Service Specific Terms quy định:

- **Toạ độ (lat/lng) chỉ được cache TỐI ĐA 30 ngày liên tục**, sau đó phải xoá/làm mới.
- **`place_id`** được **miễn trừ** — lưu **vô thời hạn**. (Tương tự Google ID từ Places/
  Directions/Geolocation/Routes.)

**Hệ quả dự án**: `dataset/gazetteer.json` và bảng Postgres `gazetteer` lưu lat/lon **lâu
hơn 30 ngày** → về mặt ToS là **rủi ro tuân thủ**. Hướng giảm thiểu (chưa bắt buộc cho
đồ án, nhưng nên ghi nhận):

1. Lưu thêm `place_id` (được phép vô hạn) để **re-resolve** toạ độ khi cần thay vì giữ
   lat/lon vĩnh viễn.
2. Hoặc coi `gazetteer` là cache có TTL 30 ngày, chạy lại `build_gazetteer.py` định kỳ.
3. Với địa danh LỊCH SỬ đã đổi tên/biến mất, toạ độ là do **LLM suy** (không phải
   Google) → không thuộc ràng buộc Google.

Đây là lý do trước đây plan loại Google ("ToS cấm lưu geocode"). User đã quyết định
dùng Google; ghi caveat này để cân nhắc khi triển khai thật/đề cập trong báo cáo.

---

## 5. Nguồn (official docs)

- [Geocoding API — Get started / request](https://developers.google.com/maps/documentation/geocoding/requests-geocoding)
- [Geocoding API — Overview](https://developers.google.com/maps/documentation/geocoding/overview)
- [Geocoding — Address types & component types](https://developers.google.com/maps/documentation/geocoding/requests-geocoding#Types)
- [Geocoding — Policies & attributions](https://developers.google.com/maps/documentation/geocoding/policies)
- [Maps JavaScript API — Advanced Markers](https://developers.google.com/maps/documentation/javascript/advanced-markers/start)
- [Maps JavaScript API — Dynamic library import](https://developers.google.com/maps/documentation/javascript/load-maps-js-api)
- [Service Specific Terms (caching, 3.2.3)](https://cloud.google.com/maps-platform/terms/maps-service-terms)
