"""Gom địa danh cần geocode + rút NGỮ CẢNH cho từng địa danh từ `timeline_events`.

Thuần tất định, không chạm DB và không gọi LLM: nhận danh sách event (dict như bảng
`timeline_events` trả về), trả `{location_norm: LocationToGeocode}`. Nhờ vậy test được
mà không cần Postgres, và `build_gazetteer.py` chỉ còn việc đọc DB rồi truyền vào.

Vì sao cần ngữ cảnh: geocoder trước đây nhận đúng MỘT cái tên trần trụi, nên "đồi A1"
hay "làng Thanh Thuỷ" là bài toán không có lời giải — Google trả bừa (đã bị `_name_matches`
chặn), LLM buộc phải trả 0.0/0.0. Bốn manh mối dưới đây lấy được ngay trong cùng một
bảng, không phải join sang kho chunk:

- `anchors`   — `location_anchor` của event chứa địa danh. Mạnh nhất: theo luật trích
                (prompt timeline v9) anchor là đơn vị NHỎ NHẤT bao trọn `locations`.
- `neighbors` — địa danh khác cùng event. "Gò Công" đi với "Tân An", "Mỹ Tho" thì đó là
                Gò Công Tiền Giang, không phải một Gò Công trùng tên nào khác.
- `events`    — nhãn event, cho biết bối cảnh (ai, chiến dịch nào).
- `period`    — khoảng năm, để LLM biết địa danh đang mang tên của thời nào.

Nhãn event chọn theo tiêu chí "event ÍT địa danh nhất trước": event chỉ nhắc mỗi địa
danh này nói về nó nhiều hơn hẳn một event liệt kê 26 nơi. Sắp bằng `sorted()` trên
`(số_địa_danh, nhãn)` nên kết quả tất định, không phụ thuộc thứ tự đọc từ DB.

HAI BỘ LỌC dưới đây có mặt vì manh mối YẾU còn hại hơn không có manh mối — `anchors[0]`
đi thẳng vào truy vấn Google, nên một anchor sai lái hẳn kết quả sang nơi khác:

- `ANCHOR_MIN_SHARE`: anchor phải được ĐA SỐ event của địa danh đó ủng hộ. Đo trên 2.439
  địa danh của corpus, ngưỡng 0.5 chỉ bỏ 152 cái (48.3% -> 42.0% còn anchor) mà bỏ đúng
  toàn bộ nhóm nhiễu: "Sài Gòn" -> "Sầm Nưa" 1/179 lượt, "Huế" -> "Sơn phòng Tân Sở"
  1/103, "Hải Phòng" -> "Hà Nội" 1/71. Nhóm giữ lại chính là các tên vi mô cần anchor
  nhất: "đồi A1" -> "Điện Biên Phủ" 31/31, "A1" 19/20, "Ái Tử" -> "Quảng Trị" 10/13.
  Lý do sâu hơn: anchor là thuộc tính của EVENT, không phải của địa danh. Một event kể
  chuyện ở Sầm Nưa mà tiện nhắc Sài Gòn thì anchor của nó không nói gì về Sài Gòn cả.
- `MAX_PERIOD_SPAN`: `period` chỉ để trả lời "địa danh mang tên của thời nào". Trải hơn
  một thế hệ thì không còn "thời nào" nào cả — "Hà Nội: 1880-1982" đúng mà vô dụng.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from typing import Any

from app.indexing.graph.normalize import normalize_name
from app.schemas.gazetteer import GeocodeContext, LocationToGeocode

__all__ = [
    "collect_locations",
    "ANCHOR_MIN_SHARE",
    "MAX_ANCHORS",
    "MAX_NEIGHBORS",
    "MAX_EVENTS",
    "MAX_PERIOD_SPAN",
]

# Cắt ngắn để prompt không loãng: quá nhiều manh mối thì manh mối mạnh (anchor) bị chìm.
# MAX_ANCHORS = 2 vì ANCHOR_MIN_SHARE = 0.5 vốn đã cho tối đa 2 anchor cùng qua cửa.
MAX_ANCHORS = 2
MAX_NEIGHBORS = 5
MAX_EVENTS = 2

# Anchor phải có mặt ở ít nhất ngần này phần các event nhắc địa danh (xem docstring).
ANCHOR_MIN_SHARE = 0.5

# Số năm tối đa `period` được phép trải. Xấp xỉ một thế hệ: rộng hơn thì không còn chỉ
# về một thời kỳ nào nữa.
MAX_PERIOD_SPAN = 25

def _period(years: set[str]) -> str:
    """Khoảng năm gọn: một năm -> '1954'; nhiều năm -> '1859-1885'.

    Trải quá `MAX_PERIOD_SPAN` -> '' (không có thời kỳ nào để nói).
    """
    if not years:
        return ""
    lo, hi = min(years), max(years)
    if lo == hi:
        return lo
    if int(hi) - int(lo) > MAX_PERIOD_SPAN:
        return ""
    return f"{lo}-{hi}"

def collect_locations(
    events: Iterable[dict[str, Any]], min_count: int = 1
) -> dict[str, LocationToGeocode]:
    """Gom event -> {location_norm: LocationToGeocode}. `min_count` lọc theo số event.

    Mỗi event đóng góp MỘT lượt cho mỗi địa danh khác nhau trong `locations` (trùng lặp
    trong cùng một event chỉ tính một). `display` là surface form phổ biến nhất của nhóm.
    """
    counts: Counter[str] = Counter()
    surfaces: dict[str, Counter[str]] = defaultdict(Counter)
    anchors: dict[str, Counter[str]] = defaultdict(Counter)
    neighbors: dict[str, Counter[str]] = defaultdict(Counter)
    labels: dict[str, set[tuple[int, str]]] = defaultdict(set)
    years: dict[str, set[str]] = defaultdict(set)

    for event in events:
        raw = [str(loc).strip() for loc in (event.get("locations") or [])]
        locs = [loc for loc in dict.fromkeys(raw) if loc]  # dedup, giữ thứ tự văn bản
        if not locs:
            continue
        norms = [normalize_name(loc) for loc in locs]
        anchor = str(event.get("location_anchor") or "").strip()
        anchor_norm = normalize_name(anchor) if anchor else ""
        label = str(event.get("label") or "").strip()
        year = str(event.get("time_start") or "")[:4]

        for loc, norm in zip(locs, norms, strict=True):
            if not norm:
                continue
            counts[norm] += 1
            surfaces[norm][loc] += 1
            # Anchor trùng chính địa danh đang xét thì không phải manh mối gì thêm.
            if anchor and anchor_norm != norm:
                anchors[norm][anchor] += 1
            for other, other_norm in zip(locs, norms, strict=True):
                if other_norm != norm:
                    neighbors[norm][other] += 1
            if label:
                labels[norm].add((len(locs), label))
            if len(year) == 4 and year.isdigit():
                years[norm].add(year)

    out: dict[str, LocationToGeocode] = {}
    for norm, n in counts.items():
        if n < min_count:
            continue
        floor = n * ANCHOR_MIN_SHARE
        out[norm] = LocationToGeocode(
            norm=norm,
            display=surfaces[norm].most_common(1)[0][0],
            count=n,
            context=GeocodeContext(
                anchors=[
                    name
                    for name, hits in anchors[norm].most_common(MAX_ANCHORS)
                    if hits >= floor
                ],
                neighbors=[name for name, _ in neighbors[norm].most_common(MAX_NEIGHBORS)],
                events=[lab for _, lab in sorted(labels[norm])[:MAX_EVENTS]],
                period=_period(years[norm]),
            ),
        )
    return out
