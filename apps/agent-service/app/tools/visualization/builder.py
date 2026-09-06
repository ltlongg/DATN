"""Online: dựng `VisualizationPayload` (dòng thời gian) từ events đã retrieve.

KHÔNG trích mới. Luồng:
  retrieved_chunk_ids
   -> select_events_by_chunks (event có source_chunk_ids GIAO tập đã retrieve)
   -> event có time_start -> TimelineItem; thiếu time_start -> không render (unplaced)

Ghi chú: bộ LỌC LLM "event nào câu trả lời thực sự nhắc tới" (plan đề là tuỳ chọn) để
DÀNH cho lúc tích hợp answer flow của agent — chưa có answer_text ở giai đoạn này nên
chưa thêm (tránh phụ thuộc LLM trong online path khi chưa cần).

Bản đồ đã gỡ khỏi hệ thống 2026-09-06: khâu chuẩn hoá địa danh + tra toạ độ (gazetteer)
bỏ theo. `locations` vẫn đi cùng mốc thời gian, nhưng chỉ dạng CHỮ.
"""

from __future__ import annotations

from app.schemas.visualization import TimelineItem, VisualizationPayload
from app.tools.visualization.event_store import select_events_by_chunks

__all__ = ["build_visualization"]


def build_visualization(
    retrieved_chunk_ids: list[str], database_url: str | None = None
) -> VisualizationPayload:
    """Lấy events theo chunk đã retrieve -> payload dòng thời gian."""
    events = select_events_by_chunks(retrieved_chunk_ids, database_url)
    if not events:
        return VisualizationPayload()

    timeline: list[TimelineItem] = []
    unplaced = 0

    for event in events:
        time_start = event.get("time_start")  # None nếu cột NULL
        if not time_start:
            unplaced += 1  # không có mốc -> không render (honest)
            continue
        timeline.append(
            TimelineItem(
                event_id=event["event_id"],
                label=event["label"],
                summary=event["summary"],
                time_start=time_start,
                time_end=event.get("time_end"),
                confidence=event["confidence"],
                locations=event.get("locations") or [],
            )
        )

    return VisualizationPayload(
        timeline=timeline,
        event_count=len(events),
        unplaced_count=unplaced,
    )
