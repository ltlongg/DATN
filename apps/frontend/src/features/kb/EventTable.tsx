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
    <ul className="divide-y divide-paper-border">
      {items.map((e) => (
        <li key={e.event_id}>
          <button
            onClick={() => onSelect(e.event_id)}
            aria-pressed={e.event_id === selectedId}
            className={`w-full px-3 py-2 text-left ${
              e.event_id === selectedId ? "bg-brand/5" : "hover:bg-paper"
            }`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-ink-soft">{timeLabel(e)}</span>
              <ConfidenceBadge confidence={e.confidence} />
            </div>
            <p className="mt-0.5 text-sm text-ink">{e.label}</p>
            {e.locations.length > 0 && (
              <p className="mt-0.5 text-xs text-ink-soft">{e.locations.join(", ")}</p>
            )}
          </button>
        </li>
      ))}
    </ul>
  );
}
