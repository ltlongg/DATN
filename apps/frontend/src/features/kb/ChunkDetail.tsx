import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import type { ChunkDetail as ChunkDetailData, EntityListItem } from "@/types/kb";

/** Chi tiết chunk: full text + metadata + "được tham chiếu bởi" (event: Postgres,
 * entity: proxy Neo4j qua listEntities?chunk_id — 2 cơ chế khác store). */
export function ChunkDetail({
  detail,
  referencingEntities,
  onNavEntity,
  onNavEvent,
}: {
  detail: ChunkDetailData;
  referencingEntities: EntityListItem[];
  onNavEntity: (normName: string) => void;
  onNavEvent: (eventId: string) => void;
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
          <dl className="space-y-1 text-xs">
            {Object.entries(detail.metadata).map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <dt className="w-28 shrink-0 text-ink-soft">{k}</dt>
                <dd className="text-ink">
                  {Array.isArray(v) ? v.join(", ") : String(v ?? "")}
                </dd>
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
              <li key={e.event_id}>
                <button
                  onClick={() => onNavEvent(e.event_id)}
                  className="flex items-center gap-2 text-left text-sm text-brand hover:underline"
                >
                  <span>{e.label}</span>
                  <ConfidenceBadge confidence={e.confidence} />
                </button>
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
              <li key={ent.norm_name}>
                <button
                  onClick={() => onNavEntity(ent.norm_name)}
                  className="rounded-full border border-paper-border px-2 py-0.5 text-xs text-brand hover:border-brand"
                >
                  {ent.name}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
