import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import type { ChunkDetail as ChunkDetailData, EntityListItem } from "@/types/kb";

/** Metadata là JSONB tự do: ngoài scalar/mảng còn có dict (`headings` = {h1, h2...}) —
 * String() trên dict ra "[object Object]" nên phải duyệt đệ quy. */
function formatMetaValue(v: unknown): string {
  if (v === null || v === undefined) return "";
  if (Array.isArray(v)) return v.map(formatMetaValue).join(", ");
  if (typeof v === "object") {
    return Object.entries(v as Record<string, unknown>)
      .map(([k, val]) => `${k}: ${formatMetaValue(val)}`)
      .join(" · ");
  }
  return String(v);
}

/** Chi tiết chunk: full text + metadata + "được tham chiếu bởi" (event: Postgres,
 * entity: proxy Neo4j qua listEntities?chunk_id — 2 cơ chế khác store). */
export function ChunkDetail({
  detail,
  referencingEntities,
}: {
  detail: ChunkDetailData;
  referencingEntities: EntityListItem[];
}) {
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs text-ink-soft">
          {detail.heading_path.length > 0 ? detail.heading_path.join(" › ") : detail.chunk_id}
        </p>
        <pre className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap rounded-md bg-paper p-3 font-sans text-sm text-ink">
          {detail.text}
        </pre>
      </div>

      {Object.keys(detail.metadata).length > 0 && (
        <section>
          <p className="mb-1 text-xs font-semibold uppercase text-ink-soft">Metadata</p>
          {/* grid thay vì width cứng: key dài (extracted_prompt_version) tự nới cột, không đè giá trị */}
          <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-xs">
            {Object.entries(detail.metadata).map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-ink-soft">{k}</dt>
                <dd className="min-w-0 break-words text-ink">{formatMetaValue(v)}</dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      <section>
        <p className="mb-1 text-xs font-semibold uppercase text-ink-soft">
          Sự kiện tham chiếu ({detail.referencing_events.length})
        </p>
        {detail.referencing_events.length === 0 ? (
          <p className="text-xs text-ink-soft">Không có.</p>
        ) : (
          <ul className="space-y-1">
            {detail.referencing_events.map((e) => (
              <li key={e.event_id} className="flex items-center gap-2 text-sm text-ink">
                <span>{e.label}</span>
                <ConfidenceBadge confidence={e.confidence} />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <p className="mb-1 text-xs font-semibold uppercase text-ink-soft">
          Thực thể tham chiếu ({referencingEntities.length})
        </p>
        {referencingEntities.length === 0 ? (
          <p className="text-xs text-ink-soft">Không có.</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {referencingEntities.map((ent) => (
              <li
                key={ent.norm_name}
                className="rounded-full border border-paper-border px-2 py-0.5 text-xs text-ink"
              >
                {ent.name}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
