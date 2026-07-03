import { EventMap } from "@/features/map/EventMap";
import { useChatUiStore } from "@/store/chatUiStore";
import type { VisualizationPayload } from "@/types";

/**
 * Panel bản đồ (timeline đã tách thành TimelineBar ngang full-width ở AskPage),
 * liên kết với timeline qua selectedEventId. Honest fallback tự xử lý trong EventMap
 * (markers rỗng -> empty-state).
 */
export function VizPanel({ visualization }: { visualization: VisualizationPayload }) {
  const closeViz = useChatUiStore((s) => s.closeViz);

  return (
    <div className="flex flex-1 flex-col border-l border-paper-border">
      <div className="flex items-center justify-between border-b border-paper-border bg-paper-card px-4 py-2">
        <span className="text-sm font-medium text-ink">
          {visualization.event_count} sự kiện
          {visualization.unplaced_count > 0 && (
            <span className="ml-2 text-xs text-ink-soft">
              ({visualization.unplaced_count} chưa đủ dữ liệu hiển thị)
            </span>
          )}
        </span>
        <button onClick={closeViz} className="text-sm text-ink-soft hover:text-brand">
          Đóng ✕
        </button>
      </div>

      <div className="min-h-0 flex-1">
        <EventMap markers={visualization.markers} />
      </div>
    </div>
  );
}
