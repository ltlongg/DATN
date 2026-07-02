import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getEntity, listEntities } from "@/api/kb";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import { EntityDetail } from "@/features/kb/EntityDetail";
import { EntityTable } from "@/features/kb/EntityTable";
import { KbSearchBar } from "@/features/kb/KbSearchBar";
import { Pagination } from "@/features/kb/Pagination";

const LIMIT = 20;

export function GraphTab({
  selectedNorm,
  onSelectEntity,
  onNavChunk,
}: {
  selectedNorm: string | null;
  onSelectEntity: (normName: string) => void;
  onNavChunk: (chunkId: string) => void;
}) {
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);

  const list = useQuery({
    queryKey: ["kb-entities", q, offset],
    queryFn: () => listEntities({ q: q || undefined, limit: LIMIT, offset }),
  });
  const detail = useQuery({
    queryKey: ["kb-entity", selectedNorm],
    queryFn: () => getEntity(selectedNorm as string),
    enabled: !!selectedNorm,
  });

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <div className="space-y-3">
        <KbSearchBar
          placeholder="Tìm thực thể theo tên…"
          onSearch={(v) => {
            setQ(v);
            setOffset(0);
          }}
        />
        <div className="rounded-lg border border-paper-border bg-paper-card">
          {list.isLoading ? (
            <div className="p-4">
              <Spinner />
            </div>
          ) : list.isError ? (
            <p className="p-4 text-sm text-rose-700">Không tải được danh sách thực thể.</p>
          ) : !list.data || list.data.items.length === 0 ? (
            <EmptyState>Chưa có thực thể nào (graph có thể chưa index).</EmptyState>
          ) : (
            <EntityTable
              items={list.data.items}
              selectedNorm={selectedNorm}
              onSelect={onSelectEntity}
            />
          )}
        </div>
        {list.data && (
          <Pagination
            total={list.data.total}
            limit={LIMIT}
            offset={offset}
            onChange={setOffset}
          />
        )}
      </div>

      <div className="rounded-lg border border-paper-border bg-paper-card p-4">
        {!selectedNorm ? (
          <p className="text-sm text-ink-soft">Chọn một thực thể để xem ego-graph.</p>
        ) : detail.isLoading ? (
          <Spinner />
        ) : detail.isError || !detail.data ? (
          <p className="text-sm text-rose-700">Không tải được chi tiết thực thể.</p>
        ) : (
          <EntityDetail
            detail={detail.data}
            onNavChunk={onNavChunk}
            onSelectEntity={onSelectEntity}
          />
        )}
      </div>
    </div>
  );
}
