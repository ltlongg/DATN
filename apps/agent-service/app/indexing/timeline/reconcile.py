"""Reconcile atomic event: gán `event_id` tất định + dedup xuyên chunk + `parent_event_norm`.

Đọc cache `timeline_extractions.json` ({chunk_id: {prompt_version, unit_id, events:[...]}}),
sinh danh sách record sẵn sàng nạp vào bảng `timeline_events`. THUẦN TẤT ĐỊNH (uuid5),
KHÔNG gọi LLM — chạy lại cùng cache ra cùng kết quả.

- `event_id = uuid5(NS, norm_parent | norm_time | norm_anchor | norm_label)`. Có
  `norm_parent` trong khoá để hai sự kiện KHÁC chiến dịch mà trùng time+nơi+label không
  bị gộp nhầm (xem plan §3).
- Dedup: event cùng `event_id` (từ nhiều chunk, vd một diễn biến được kể tiếp ở chunk kề)
  gộp làm MỘT: hợp nhất `source_chunk_ids` + `locations`, giữ `confidence` cao nhất và
  label/summary của bản chắc hơn.
- `parent_event_norm = resolve(parent_event)` (canonical_norm) -> gom nhóm + link sang
  node Sự kiện Neo4j. Rỗng nếu sự kiện đứng rời.

v8 đổi thành phần thứ ba của khoá từ `locations[0]` sang `location_anchor`. `locations[0]`
là "tên xuất hiện đầu câu" nên đổi theo cách diễn đạt của từng chunk — cùng một trận đánh
kể ở hai chunk mà liệt kê địa danh khác thứ tự sẽ tách thành hai sự kiện trên timeline.
Anchor là "vùng bao trùm diễn biến" nên ổn định hơn hẳn.

Cache được ghi bằng `AtomicEvent.model_dump()` (Structured Outputs strict) nên MỌI event
trong cache luôn có đủ `location_anchor`/`location_scope`/`location_source` với giá trị
thuộc enum — không cần đường lùi cho bản ghi thiếu trường. Đổi prompt mà giữ cache cũ ->
xoá `timeline_extractions.json` rồi trích lại, đừng vá ở đây.

LƯU Ý tất định: vì `parent_norm` vào khoá `event_id` qua `resolve()` (đọc
`dataset/alias_map.json`), id chỉ ổn định khi alias_map KHÔNG đổi. Build lại alias_map
-> event_id của các sự kiện CÓ parent có thể đổi. Không sao với thiết kế hiện tại (bảng
nạp lại trọn bộ TRUNCATE+insert), nhưng đừng dựa vào event_id cũ sau khi rebuild alias.

PROVENANCE CẤP CHUNK: `source_chunk_ids` của mỗi event lấy từ chính KHOÁ NGOÀI CÙNG của
cache (một chunk_id), KHÔNG phải cả unit. Nhờ vậy UI join `source_chunk_ids && retrieved`
chỉ kéo về event mà chunk được cite thực sự làm bằng chứng, thay vì mọi event cùng unit.
Event trải nhiều chunk gom lại đúng bấy nhiêu chunk qua bước dedup ở trên.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.indexing.graph.alias import resolve
from app.indexing.graph.normalize import normalize_name
from app.schemas.timeline import CONFIDENCE_RANK

__all__ = ["reconcile_events", "EVENT_ID_NAMESPACE"]

# Namespace cố định cho uuid5: dẫn xuất tất định, không đổi giữa các lần chạy ->
# cùng nội dung sự kiện luôn cho cùng event_id (idempotent, không ngẫu nhiên).
EVENT_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "vfs:timeline_events")

# Khi hai chunk kể cùng một sự kiện mà lệch `location_scope`, giữ bản THẬN TRỌNG hơn:
# 'area' (không chấm marker) thắng 'sites' (có chấm). Đoán sai theo hướng 'sites' đẻ ra
# marker ở nơi sự kiện không thực sự xảy ra; đoán sai theo hướng 'area' chỉ mất một
# marker lẽ ra vẽ được. Cùng nguyên tắc "thà bỏ sót còn hơn bịa nơi" của extractor.
_SCOPE_MERGE_RANK: dict[str, int] = {"none": 0, "sites": 1, "area": 2}

# Ngược lại với scope: `location_source` là chuyện BẰNG CHỨNG, không phải rủi ro. Chỉ cần
# MỘT chunk nêu địa điểm ngay trong câu thì địa điểm đó có bằng chứng trực tiếp -> 'text'
# thắng 'context'.
_SOURCE_MERGE_RANK: dict[str, int] = {"none": 0, "context": 1, "text": 2}

def _merge_by_rank(rank: dict[str, int], current: str, incoming: str) -> str:
    """Chọn giá trị có hạng cao hơn theo bảng `rank`; giá trị lạ coi như hạng thấp nhất."""
    return incoming if rank.get(incoming, -1) > rank.get(current, -1) else current

def _dedup_keep_order(items: list[str]) -> list[str]:
    """Loại trùng giữ thứ tự xuất hiện trong văn bản."""
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out

def _compute_event_id(
    parent_norm: str, time_start: str, anchor_norm: str, label_norm: str
) -> str:
    key = f"{parent_norm}|{time_start}|{anchor_norm}|{label_norm}"
    return str(uuid.uuid5(EVENT_ID_NAMESPACE, key))

def reconcile_events(cache: dict[str, Any]) -> list[dict[str, Any]]:
    """Cache trích (khoá theo chunk_id) -> record cho `timeline_events` (dedup + event_id)."""
    merged: dict[str, dict[str, Any]] = {}

    for chunk_id, entry in cache.items():
        for ev in entry.get("events", []):
            label = (ev.get("label") or "").strip()
            if not label:
                continue  # không có nhãn -> không định danh được, bỏ

            time_start = (ev.get("time_start") or "").strip()
            locations = [loc.strip() for loc in (ev.get("locations") or []) if loc and loc.strip()]
            anchor = (ev.get("location_anchor") or "").strip()
            scope = ev.get("location_scope") or "none"
            source = ev.get("location_source") or "none"
            parent_raw = (ev.get("parent_event") or "").strip()
            parent_norm = resolve(parent_raw)[1] if parent_raw else ""
            conf = ev.get("confidence") or "thấp"

            event_id = _compute_event_id(
                parent_norm, time_start, normalize_name(anchor) if anchor else "",
                normalize_name(label),
            )

            existing = merged.get(event_id)
            if existing is None:
                merged[event_id] = {
                    "event_id": event_id,
                    "label": label,
                    "summary": (ev.get("summary") or "").strip(),
                    "time_start": time_start,
                    "time_end": (ev.get("time_end") or "").strip(),
                    "locations": list(locations),
                    "location_anchor": anchor,  # '' -> event_store ghi NULL
                    "location_scope": scope,
                    "location_source": source,
                    "confidence": conf,
                    "parent_event_norm": parent_norm,  # '' -> event_store ghi NULL
                    "source_chunk_ids": [chunk_id],
                }
                continue

            # Gộp trùng (cùng event_id từ chunk khác) -> union chunk nguồn.
            existing["locations"] = _dedup_keep_order(existing["locations"] + locations)
            existing["source_chunk_ids"] = _dedup_keep_order(
                existing["source_chunk_ids"] + [chunk_id]
            )
            existing["location_scope"] = _merge_by_rank(
                _SCOPE_MERGE_RANK, existing["location_scope"], scope
            )
            existing["location_source"] = _merge_by_rank(
                _SOURCE_MERGE_RANK, existing["location_source"], source
            )
            if CONFIDENCE_RANK.get(conf, 0) > CONFIDENCE_RANK.get(existing["confidence"], 0):
                existing["confidence"] = conf
                existing["label"] = label
                existing["summary"] = (ev.get("summary") or "").strip()
            if not existing["time_end"] and ev.get("time_end"):
                existing["time_end"] = ev["time_end"].strip()

    records = list(merged.values())
    # Sắp tất định: theo thời gian (rỗng cuối) rồi label — dễ đọc khi soi, test ổn định.
    records.sort(key=lambda r: (r["time_start"] == "", r["time_start"], r["label"]))
    return records
