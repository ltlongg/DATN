import { CalendarDays } from "lucide-react";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import type { EventDetail as EventDetailData } from "@/types/kb";

function timeLabel(e: EventDetailData): string {
  if (!e.time_start) return "—";
  if (e.time_end && e.time_end !== e.time_start) return `${e.time_start} – ${e.time_end}`;
  return e.time_start;
}

/** Chi tiết event: summary + thời gian + locations + chunk nguồn (id để tra cứu). Gazetteer
 * hoãn -> không có toạ độ (đúng chủ ý). */
export function EventDetail({ detail }: { detail: EventDetailData }) {
  return (
    <div className="space-y-6">
      <div>
        <div className="flex flex-wrap items-center gap-2.5">
          <h2 className="text-xl font-semibold text-ink">{detail.label}</h2>
          <ConfidenceBadge confidence={detail.confidence} />
        </div>
        <p className="mt-1.5 flex items-center gap-1.5 text-sm tabular-nums text-brand">
          <CalendarDays size={14} aria-hidden />
          {timeLabel(detail)}
        </p>
      </div>

      <p className="text-sm leading-7 text-ink">{detail.summary}</p>

      <div className="grid grid-cols-2 gap-4 rounded-lg bg-paper-sunken/60 p-4 text-sm">
        <div>
          <p className="section-title mb-1">Địa điểm</p>
          <p className="text-ink">
            {detail.locations.length > 0 ? detail.locations.join(", ") : "—"}
          </p>
        </div>
        <div>
          <p className="section-title mb-1">Sự kiện cha</p>
          <p className="text-ink">{detail.parent_event_norm ?? "—"}</p>
        </div>
      </div>

      <section>
        <p className="section-title mb-2">Chunk nguồn</p>
        {detail.source_chunk_ids.length === 0 ? (
          <span className="text-xs text-ink-faint">—</span>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {detail.source_chunk_ids.map((id) => (
              <span
                key={id}
                className="badge badge-neutral font-mono text-[11px]"
              >
                {id}
              </span>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
