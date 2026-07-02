import { TimelineRow } from "@/features/timeline/TimelineRow";
import type { TimelineItem } from "@/types";

/** Sắp xếp theo time_start (best-effort theo chuỗi — dữ liệu đã chuẩn hoá ở indexing). */
function sortByTime(items: TimelineItem[]): TimelineItem[] {
  return [...items].sort((a, b) => a.time_start.localeCompare(b.time_start, "vi"));
}

export function Timeline({ items }: { items: TimelineItem[] }) {
  if (items.length === 0) {
    return (
      <div className="p-4 text-sm text-ink-soft">Chưa có mốc thời gian cho câu trả lời này.</div>
    );
  }
  return (
    <ol className="space-y-2 p-3">
      {sortByTime(items).map((item) => (
        <TimelineRow key={item.event_id} item={item} />
      ))}
    </ol>
  );
}
