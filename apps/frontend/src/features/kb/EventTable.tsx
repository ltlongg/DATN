import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import type { EventListItem } from "@/types/kb";

function timeLabel(e: EventListItem): string {
  if (!e.time_start) return "—";
  if (e.time_end && e.time_end !== e.time_start) return `${e.time_start} – ${e.time_end}`;
  return e.time_start;
}

export function EventTable({
  items,
  selectedId,
  onSelect,
}: {
  items: EventListItem[];
  selectedId: string | null;
  onSelect: (eventId: string) => void;
}) {
  return (
    <ul className="space-y-0.5">
      {items.map((e) => (
        <li key={e.event_id}>
          <button
            onClick={() => onSelect(e.event_id)}
            aria-pressed={e.event_id === selectedId}
            className={`item-row ${e.event_id === selectedId ? "item-row-active" : ""}`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs font-medium tabular-nums text-brand">{timeLabel(e)}</span>
              <ConfidenceBadge confidence={e.confidence} />
            </div>
            <p className="mt-1 text-sm font-medium text-ink">{e.label}</p>
            {e.locations.length > 0 && (
              <p className="mt-0.5 text-xs text-ink-soft">{e.locations.join(", ")}</p>
            )}
          </button>
        </li>
      ))}
    </ul>
  );
}
