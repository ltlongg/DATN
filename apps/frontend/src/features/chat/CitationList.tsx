import type { Citation } from "@/types";

function locationLabel(c: Citation): string {
  if (!c.source_file) return c.chunk_id;
  if (c.start_line != null && c.end_line != null) {
    return `${c.source_file}:${c.start_line}-${c.end_line}`;
  }
  return c.source_file;
}

/** Danh sách nguồn: heading_path (breadcrumb) + vị trí dòng + trích dẫn (nếu có). */
export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <div className="mt-3 space-y-2 border-t border-paper-border pt-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">Nguồn</p>
      <ol className="space-y-2">
        {citations.map((c, i) => (
          <li key={`${c.chunk_id}-${i}`} className="text-xs text-ink-soft">
            <span className="mr-1 font-medium text-ink">[{i + 1}]</span>
            {c.heading_path.length > 0 && (
              <span className="text-ink">{c.heading_path.join(" › ")}</span>
            )}
            <span className="ml-1 text-ink-soft">— {locationLabel(c)}</span>
            {c.quote && (
              <blockquote className="mt-1 border-l-2 border-paper-border pl-2 italic">
                “{c.quote}”
              </blockquote>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}
