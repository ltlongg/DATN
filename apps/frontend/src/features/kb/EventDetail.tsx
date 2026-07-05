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
    <div className="space-y-4">
      <div>
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold text-ink">{detail.label}</h3>
          <ConfidenceBadge confidence={detail.confidence} />
        </div>
        <p className="text-xs text-ink-soft">{timeLabel(detail)}</p>
      </div>

      <p className="text-sm text-ink">{detail.summary}</p>

      <div className="grid grid-cols-2 gap-3 text-xs">
        <div>
          <p className="font-semibold uppercase text-ink-soft">Địa điểm</p>
          <p className="text-ink">
            {detail.locations.length > 0 ? detail.locations.join(", ") : "—"}
          </p>
        </div>
        <div>
          <p className="font-semibold uppercase text-ink-soft">Sự kiện cha</p>
          <p className="text-ink">{detail.parent_event_norm ?? "—"}</p>
        </div>
      </div>

      <section>
        <p className="mb-1 text-xs font-semibold uppercase text-ink-soft">Chunk nguồn</p>
        {detail.source_chunk_ids.length === 0 ? (
          <span className="text-xs text-ink-soft">—</span>
        ) : (
          <div className="flex flex-wrap gap-1">
            {detail.source_chunk_ids.map((id) => (
              <span
                key={id}
                className="rounded-full border border-paper-border px-2 py-0.5 text-[11px] text-ink"
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
