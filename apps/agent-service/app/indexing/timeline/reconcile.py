"""Reconcile atomic event: gán `event_id` tất định + dedup xuyên chunk + `parent_event_norm`.

Đọc cache `timeline_extractions.json` ({chunk_id: {prompt_version, unit_id, events:[...]}}),
sinh danh sách record sẵn sàng nạp vào bảng `timeline_events`. THUẦN TẤT ĐỊNH (uuid5),
KHÔNG gọi LLM — chạy lại cùng cache ra cùng kết quả.

- `event_id = uuid5(NS, norm_parent | norm_time | norm_location0 | norm_label)`. Có
  `norm_parent` trong khoá để hai sự kiện KHÁC chiến dịch mà trùng time+nơi+label không
  bị gộp nhầm (xem plan §3).
- Dedup: event cùng `event_id` (từ nhiều chunk, vd một diễn biến được kể tiếp ở chunk kề)
  gộp làm MỘT: hợp nhất `source_chunk_ids` + `locations`, giữ `confidence` cao nhất và
  label/summary của bản chắc hơn.
- `parent_event_norm = resolve(parent_event)` (canonical_norm) -> gom nhóm + link sang
  node Sự kiện Neo4j. Rỗng nếu sự kiện đứng rời.
- `seq` = vị trí trong mảng `events` của chunk gặp đầu tiên -> giữ MẠCH KỂ của sách cho
  các event cùng chunk (khoá sort thứ ba của feed timeline).

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

import re
import uuid
from typing import Any

from app.indexing.graph.alias import resolve
from app.indexing.graph.normalize import normalize_name
from app.schemas.timeline import CONFIDENCE_RANK

__all__ = ["reconcile_events", "time_sort_key", "EVENT_ID_NAMESPACE"]

# Namespace cố định cho uuid5: dẫn xuất tất định, không đổi giữa các lần chạy ->
# cùng nội dung sự kiện luôn cho cùng event_id (idempotent, không ngẫu nhiên).
EVENT_ID_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "vfs:timeline_events")

_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}

# Năm 1-4 chữ số, tuỳ chọn -tháng, tuỳ chọn -ngày (hậu tố ' TCN' đã bị cắt trước khi khớp).
_YEAR_RE = re.compile(r"^(\d{1,4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?$")
_ROMAN_RE = re.compile(r"^[IVXLCDM]+$")


def _roman_to_int(text: str) -> int:
    total = 0
    prev = 0
    for char in reversed(text):
        value = _ROMAN_VALUES[char]
        total += -value if value < prev else value
        prev = max(prev, value)
    return total


def time_sort_key(time_start: str | None) -> float | None:
    """`time_start` -> số thực để ORDER BY. Không parse được -> None (mốc rác, không lên
    trang timeline). TCN thành số âm; thế kỷ lấy năm ĐẦU thế kỷ (XII -> 1101, III TCN ->
    -300) nên nằm trước mọi mốc trong chính thế kỷ đó."""
    if not time_start:
        return None

    text = time_start.strip()
    is_bc = text.endswith(" TCN")
    if is_bc:
        text = text[: -len(" TCN")].strip()

    match = _YEAR_RE.match(text)
    if match:
        year = int(match.group(1))
        month = int(match.group(2)) if match.group(2) else 1
        day = int(match.group(3)) if match.group(3) else 1
        # Phần lẻ luôn CỘNG vào, kể cả TCN: trong năm 179 TCN thì tháng 3 muộn hơn đầu năm.
        offset = (month - 1) / 12 + (day - 1) / 365
        return (-year if is_bc else year) + offset

    if _ROMAN_RE.match(text):
        century = _roman_to_int(text)
        return -century * 100 if is_bc else (century - 1) * 100 + 1

    return None


def _dedup_keep_order(items: list[str]) -> list[str]:
    """Loại trùng giữ thứ tự xuất hiện (locations[0] chính vẫn đứng đầu)."""
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it and it not in seen:
            seen.add(it)
            out.append(it)
    return out


def _compute_event_id(
    parent_norm: str, time_start: str, loc0_norm: str, label_norm: str
) -> str:
    key = f"{parent_norm}|{time_start}|{loc0_norm}|{label_norm}"
    return str(uuid.uuid5(EVENT_ID_NAMESPACE, key))


def reconcile_events(cache: dict[str, Any]) -> list[dict[str, Any]]:
    """Cache trích (khoá theo chunk_id) -> record cho `timeline_events` (dedup + event_id)."""
    merged: dict[str, dict[str, Any]] = {}

    for chunk_id, entry in cache.items():
        for seq, ev in enumerate(entry.get("events", [])):
            label = (ev.get("label") or "").strip()
            if not label:
                continue  # không có nhãn -> không định danh được, bỏ

            time_start = (ev.get("time_start") or "").strip()
            locations = [loc.strip() for loc in (ev.get("locations") or []) if loc and loc.strip()]
            loc0_norm = normalize_name(locations[0]) if locations else ""
            parent_raw = (ev.get("parent_event") or "").strip()
            parent_norm = resolve(parent_raw)[1] if parent_raw else ""
            conf = ev.get("confidence") or "thấp"

            event_id = _compute_event_id(
                parent_norm, time_start, loc0_norm, normalize_name(label)
            )

            existing = merged.get(event_id)
            if existing is None:
                merged[event_id] = {
                    "event_id": event_id,
                    "label": label,
                    "summary": (ev.get("summary") or "").strip(),
                    "time_start": time_start,
                    "time_sort": time_sort_key(time_start),
                    "time_end": (ev.get("time_end") or "").strip(),
                    "locations": list(locations),
                    "confidence": conf,
                    "parent_event_norm": parent_norm,  # '' -> event_store ghi NULL
                    "source_chunk_ids": [chunk_id],
                    "seq": seq,
                }
                continue

            # Gộp trùng (cùng event_id từ chunk khác) -> union chunk nguồn.
            existing["locations"] = _dedup_keep_order(existing["locations"] + locations)
            existing["source_chunk_ids"] = _dedup_keep_order(
                existing["source_chunk_ids"] + [chunk_id]
            )
            if CONFIDENCE_RANK.get(conf, 0) > CONFIDENCE_RANK.get(existing["confidence"], 0):
                existing["confidence"] = conf
                existing["label"] = label
                existing["summary"] = (ev.get("summary") or "").strip()
            if not existing["time_end"] and ev.get("time_end"):
                existing["time_end"] = ev["time_end"].strip()

    records = list(merged.values())
    records.sort(key=lambda r: (r["time_sort"] is None, r["time_sort"] or 0.0, r["label"]))
    return records
