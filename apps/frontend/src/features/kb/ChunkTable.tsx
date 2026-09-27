import type { ChunkListItem } from "@/types/kb";

function lineLabel(c: ChunkListItem): string {
  if (c.source_file && c.start_line != null && c.end_line != null) {
    return `${c.source_file}:${c.start_line}-${c.end_line}`;
  }
  return c.source_file ?? "";
}

export function ChunkTable({
  items,
  selectedId,
  onSelect,
}: {
  items: ChunkListItem[];
  selectedId: string | null;
  onSelect: (chunkId: string) => void;
}) {
  return (
    <ul className="space-y-0.5">
      {items.map((c) => (
        <li key={c.chunk_id}>
          <button
            onClick={() => onSelect(c.chunk_id)}
            aria-pressed={c.chunk_id === selectedId}
            className={`item-row ${c.chunk_id === selectedId ? "item-row-active" : ""}`}
          >
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-xs text-ink-soft">
                {c.heading_path.length > 0 ? c.heading_path.join(" › ") : c.chunk_id}
              </span>
              <span className="shrink-0 font-mono text-[11px] text-ink-faint">{lineLabel(c)}</span>
            </div>
            <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-ink">{c.preview}</p>
          </button>
        </li>
      ))}
    </ul>
  );
}
