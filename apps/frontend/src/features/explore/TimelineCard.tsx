import { MapPin } from "lucide-react";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { durationLabel, shortTime } from "@/features/timeline/timeFormat";
import type { TimelineCardItem } from "@/types/timeline";

const MAX_LOCATIONS = 3;

/** Chấm độ tin cậy: 89% sự kiện là "cao" nên in pill chữ lên từng thẻ chỉ là nhiễu —
 * dạng chữ để dành cho phần trải ra (ConfidenceBadge). */
const DOT_CLASS: Record<string, string> = {
  cao: "bg-brand",
  vừa: "bg-brand/55",
  thấp: "bg-brand/30",
};

export function TimelineCard({
  card,
  alignRight,
  expanded,
  onToggle,
}: {
  card: TimelineCardItem;
  /** Thẻ nằm bên TRÁI trục (md trở lên) -> canh phải cho sát trục. */
  alignRight: boolean;
  expanded: boolean;
  onToggle: () => void;
}) {
  const isRange = Boolean(card.time_end && card.time_end !== card.time_start);
  const duration = isRange ? durationLabel(card.time_start, card.time_end) : null;
  const locations = card.locations.slice(0, MAX_LOCATIONS);

  return (
    <button
      onClick={onToggle}
      aria-expanded={expanded}
      className={`card w-full px-4 py-3 text-left transition hover:border-brand/40 hover:shadow-pop ${
        expanded ? "border-brand/40" : ""
      } ${alignRight ? "md:text-right" : ""}`}
    >
      <span className={`flex items-baseline gap-2 ${alignRight ? "md:flex-row-reverse" : ""}`}>
        <span
          aria-hidden
          title={`độ tin cậy: ${card.confidence}`}
          className={`mt-1 h-1.5 w-1.5 shrink-0 rounded-full ${
            DOT_CLASS[card.confidence] ?? "bg-ink-soft/40"
          }`}
        />
        <span className="font-serif text-[15px] font-semibold leading-snug text-ink">
          {card.label}
        </span>
      </span>

      {isRange && (
        <span className="mt-1 block text-xs tabular-nums text-brand">
          → {shortTime(card.time_end as string)}
          {duration && ` · ${duration}`}
        </span>
      )}

      {locations.length > 0 && (
        <span
          className={`mt-1 flex items-center gap-1 text-xs text-ink-soft ${
            alignRight ? "md:justify-end" : ""
          }`}
        >
          <MapPin size={12} className="shrink-0 text-ink-faint" aria-hidden />
          {locations.join(" · ")}
        </span>
      )}

      {expanded && (
        <span className="mt-3 block border-t border-paper-border pt-3">
          <span className="block text-xs leading-relaxed text-ink-soft">{card.summary}</span>
          <span className="mt-2 block">
            <ConfidenceBadge confidence={card.confidence} />
          </span>
        </span>
      )}
    </button>
  );
}
