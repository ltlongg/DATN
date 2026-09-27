import type { EntityListItem } from "@/types/kb";

export function EntityTable({
  items,
  selectedNorm,
  onSelect,
}: {
  items: EntityListItem[];
  selectedNorm: string | null;
  onSelect: (normName: string) => void;
}) {
  return (
    <ul className="space-y-0.5">
      {items.map((e) => (
        <li key={e.norm_name}>
          <button
            onClick={() => onSelect(e.norm_name)}
            aria-pressed={e.norm_name === selectedNorm}
            className={`item-row flex items-center justify-between gap-2 ${
              e.norm_name === selectedNorm ? "item-row-active" : ""
            }`}
          >
            <span className="truncate text-sm font-medium text-ink">{e.name}</span>
            <span className="shrink-0 text-xs text-ink-soft">
              {e.type ?? "—"} · {e.source_chunk_count} chunk
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
