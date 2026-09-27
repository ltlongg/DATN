import { EgoGraph } from "@/features/kb/EgoGraph";
import type { EntityDetail as EntityDetailData } from "@/types/kb";

function ChunkChips({ ids }: { ids: string[] }) {
  if (ids.length === 0) return <span className="text-xs text-ink-faint">—</span>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {ids.map((id) => (
        <span
          key={id}
          className="badge badge-neutral font-mono text-[11px]"
        >
          {id}
        </span>
      ))}
    </div>
  );
}

/** Chi tiết entity: mô tả gộp + ego-graph 1-hop + bảng quan hệ + chunk nguồn (id để tra cứu). */
export function EntityDetail({
  detail,
  onSelectEntity,
}: {
  detail: EntityDetailData;
  onSelectEntity: (normName: string) => void;
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center gap-2.5">
        <h2 className="text-xl font-semibold text-ink">{detail.name}</h2>
        <span className="badge badge-brand">{detail.type ?? "—"}</span>
      </div>

      {detail.descriptions.length > 0 && (
        <section>
          <p className="section-title mb-2">Mô tả</p>
          <ul className="list-disc space-y-1 pl-5 text-sm leading-relaxed text-ink marker:text-brand/60">
            {detail.descriptions.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <p className="section-title mb-2">Quan hệ 1-hop</p>
        <EgoGraph detail={detail} onSelectEntity={onSelectEntity} />
      </section>

      {detail.edges.length > 0 && (
        <section>
          <p className="section-title mb-2">Danh sách quan hệ</p>
          <div className="overflow-hidden rounded-lg border border-paper-border">
            <table className="data-table text-xs">
              <thead>
                <tr>
                  <th className="px-3 py-2">Nguồn</th>
                  <th className="px-3 py-2">Quan hệ</th>
                  <th className="px-3 py-2">Đích</th>
                </tr>
              </thead>
              <tbody>
                {detail.edges.map((e, i) => (
                  <tr key={i}>
                    <td className="px-3 py-2">{e.source_name ?? "—"}</td>
                    <td className="px-3 py-2 italic text-ink-soft">{e.keyword ?? "—"}</td>
                    <td className="px-3 py-2">{e.target_name ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section>
        <p className="section-title mb-2">Chunk nguồn</p>
        <ChunkChips ids={detail.source_chunk_ids} />
      </section>
    </div>
  );
}
