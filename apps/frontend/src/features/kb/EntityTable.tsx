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
    <ul className="divide-y divide-paper-border">
      {items.map((e) => (
        <li key={e.norm_name}>
          <button
            onClick={() => onSelect(e.norm_name)}
            aria-pressed={e.norm_name === selectedNorm}
            className={`flex w-full items-center justify-between gap-2 px-3 py-2 text-left ${
              e.norm_name === selectedNorm ? "bg-brand/5" : "hover:bg-paper"
            }`}
          >
            <span className="truncate text-sm text-ink">{e.name}</span>
            <span className="shrink-0 text-xs text-ink-soft">
              {e.type ?? "—"} · {e.source_chunk_count} chunk
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}
