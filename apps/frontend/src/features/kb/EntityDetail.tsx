import { EgoGraph } from "@/features/kb/EgoGraph";
import type { EntityDetail as EntityDetailData } from "@/types/kb";

function ChunkChips({
  ids,
  onNavChunk,
}: {
  ids: string[];
  onNavChunk: (chunkId: string) => void;
}) {
  if (ids.length === 0) return <span className="text-xs text-ink-soft">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {ids.map((id) => (
        <button
          key={id}
          onClick={() => onNavChunk(id)}
          className="rounded-full border border-paper-border px-2 py-0.5 text-[11px] text-brand hover:border-brand"
        >
          {id}
        </button>
      ))}
    </div>
  );
}

/** Chi tiết entity: mô tả gộp + ego-graph 1-hop + bảng quan hệ + link chunk nguồn. */
export function EntityDetail({
  detail,
  onNavChunk,
  onSelectEntity,
}: {
  detail: EntityDetailData;
  onNavChunk: (chunkId: string) => void;
  onSelectEntity: (normName: string) => void;
}) {
  return (
    <div className="space-y-4">
      <div>
        <h3 className="text-lg font-semibold text-ink">{detail.name}</h3>
        <p className="text-xs text-ink-soft">{detail.type ?? "—"}</p>
      </div>

      {detail.descriptions.length > 0 && (
        <section>
          <p className="mb-1 text-xs font-semibold uppercase text-ink-soft">Mô tả</p>
          <ul className="list-disc space-y-0.5 pl-5 text-sm text-ink">
            {detail.descriptions.map((d, i) => (
              <li key={i}>{d}</li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <p className="mb-1 text-xs font-semibold uppercase text-ink-soft">Quan hệ 1-hop</p>
        <EgoGraph detail={detail} onSelectEntity={onSelectEntity} />
      </section>

      {detail.edges.length > 0 && (
        <section>
          <p className="mb-1 text-xs font-semibold uppercase text-ink-soft">
            Danh sách quan hệ
          </p>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-ink-soft">
                <th className="py-1 pr-2 font-medium">Nguồn</th>
                <th className="py-1 pr-2 font-medium">Quan hệ</th>
                <th className="py-1 font-medium">Đích</th>
              </tr>
            </thead>
            <tbody>
              {detail.edges.map((e, i) => (
                <tr key={i} className="border-t border-paper-border align-top">
                  <td className="py-1 pr-2 text-ink">{e.source_name ?? "—"}</td>
                  <td className="py-1 pr-2 text-ink-soft">{e.keyword ?? "—"}</td>
                  <td className="py-1 text-ink">{e.target_name ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}

      <section>
        <p className="mb-1 text-xs font-semibold uppercase text-ink-soft">Chunk nguồn</p>
        <ChunkChips ids={detail.source_chunk_ids} onNavChunk={onNavChunk} />
      </section>
    </div>
  );
}
