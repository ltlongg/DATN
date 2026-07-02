import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { useChatUiStore } from "@/store/chatUiStore";
import type { TimelineItem } from "@/types";

function timeLabel(item: TimelineItem): string {
  if (item.time_end && item.time_end !== item.time_start) {
    return `${item.time_start} – ${item.time_end}`;
  }
  return item.time_start;
}

/** 1 mốc thời gian. Click -> set selectedEventId (link 2 chiều với map). */
export function TimelineRow({ item }: { item: TimelineItem }) {
  const selectedEventId = useChatUiStore((s) => s.selectedEventId);
  const setSelected = useChatUiStore((s) => s.setSelectedEvent);
  const selected = item.event_id === selectedEventId;

  return (
    <li>
      <button
        onClick={() => setSelected(item.event_id)}
        aria-pressed={selected}
        className={`w-full rounded-lg border p-3 text-left transition ${
          selected ? "border-brand bg-brand/5" : "border-paper-border bg-paper-card hover:border-brand"
        }`}
      >
        <div className="flex items-center justify-between gap-2">
          <span className="font-medium text-ink">{timeLabel(item)}</span>
          <div className="flex items-center gap-2">
            {item.located && (
              <span title="Có toạ độ trên bản đồ" className="text-brand">
                ●
              </span>
            )}
            <ConfidenceBadge confidence={item.confidence} />
          </div>
        </div>
        <p className="mt-1 text-sm font-medium text-ink">{item.label}</p>
        <p className="mt-0.5 text-xs text-ink-soft">{item.summary}</p>
      </button>
    </li>
  );
}
