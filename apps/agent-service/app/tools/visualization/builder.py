"""Online: dựng `VisualizationPayload` (map markers + timeline) từ events đã retrieve.

KHÔNG trích mới. Luồng (xem plan §2):
  retrieved_chunk_ids
   -> select_events_by_chunks (event có source_chunk_ids GIAO tập đã retrieve)
   -> normalize_name(locations[]) -> lookup_coords (gazetteer)
   -> tách markers (có lat/lon) + timeline items (có time_start), link bằng event_id
   -> honest fallback (thiếu nơi -> chỉ timeline; thiếu time -> chỉ map; thiếu cả -> bỏ)

Marker mang theo `location_scope` của event ('sites' vs 'area') để UI vẽ đúng loại — xem
`app/schemas/visualization.py`. Builder KHÔNG lọc theo scope: event 'area' vẫn ra đủ
marker, chỉ khác cách vẽ. Lọc ở đây là giấu mất địa bàn của phong trào khỏi bản đồ.

Ghi chú: bộ LỌC LLM "event nào câu trả lời thực sự nhắc tới" (plan đề là tuỳ chọn) để
DÀNH cho lúc tích hợp answer flow của agent — chưa có answer_text ở giai đoạn này nên
chưa thêm (tránh phụ thuộc LLM trong online path khi chưa cần).
"""

from __future__ import annotations

from app.indexing.graph.normalize import normalize_name
from app.schemas.timeline import CONFIDENCE_RANK
from app.schemas.visualization import MapMarker, TimelineItem, VisualizationPayload
from app.tools.visualization.event_store import select_events_by_chunks
from app.tools.visualization.gazetteer_store import lookup_coords

__all__ = ["build_visualization"]

def _weakest(a: str, b: str) -> str:
    """Trả confidence YẾU hơn (mắt xích yếu nhất): event chắc nhưng toạ độ đoán -> nhạt."""
    return a if CONFIDENCE_RANK.get(a, 0) <= CONFIDENCE_RANK.get(b, 0) else b

def build_visualization(
    retrieved_chunk_ids: list[str], database_url: str | None = None
) -> VisualizationPayload:
    """Lấy events theo chunk đã retrieve -> payload map + timeline (link bằng event_id)."""
    events = select_events_by_chunks(retrieved_chunk_ids, database_url)
    if not events:
        return VisualizationPayload()

    # Gom location_norm của mọi event -> tra toạ độ một lần.
    norm_of: dict[str, str] = {}
    for event in events:
        for loc in event.get("locations") or []:
            if loc not in norm_of:
                norm_of[loc] = normalize_name(loc)
    coords = lookup_coords(list(set(norm_of.values())), database_url) if norm_of else {}

    markers: list[MapMarker] = []
    timeline: list[TimelineItem] = []
    unplaced = 0

    for event in events:
        event_id = event["event_id"]
        time_start = event.get("time_start")  # None nếu cột NULL
        locations = event.get("locations") or []
        # Cột NOT NULL DEFAULT 'none' và query là SELECT * -> luôn có mặt. Truy cập
        # thẳng để lỗi lộ ra nếu schema lệch, thay vì âm thầm vẽ nhầm loại marker.
        scope = event["location_scope"]

        event_markers: list[MapMarker] = []
        seen_points: set[tuple[float, float]] = set()
        for loc in locations:
            row = coords.get(norm_of[loc])
            if not row or row.get("lat") is None:
                continue
            lat, lon = float(row["lat"]), float(row["lon"])
            point = (round(lat, 5), round(lon, 5))
            if point in seen_points:  # cùng event chấm trùng điểm -> bỏ
                continue
            seen_points.add(point)
            event_markers.append(
                MapMarker(
                    event_id=event_id,
                    label=event["label"],
                    summary=event["summary"],
                    location=loc,
                    lat=lat,
                    lon=lon,
                    confidence=_weakest(event["confidence"], row.get("confidence") or "thấp"),
                    time_start=time_start,
                    scope=scope,
                )
            )

        markers.extend(event_markers)
        has_marker = bool(event_markers)

        if time_start:
            timeline.append(
                TimelineItem(
                    event_id=event_id,
                    label=event["label"],
                    summary=event["summary"],
                    time_start=time_start,
                    time_end=event.get("time_end"),
                    confidence=event["confidence"],
                    locations=locations,
                    located=has_marker,
                )
            )
        elif not has_marker:
            unplaced += 1  # không time + không toạ độ -> không render (honest)

    timeline.sort(key=lambda item: (item.time_start, item.label))
    return VisualizationPayload(
        markers=markers,
        timeline=timeline,
        event_count=len(events),
        unplaced_count=unplaced,
    )
