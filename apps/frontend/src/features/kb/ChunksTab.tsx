import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getChunk, listChunks, listEntities } from "@/api/kb";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import { ChunkDetail } from "@/features/kb/ChunkDetail";
import { ChunkTable } from "@/features/kb/ChunkTable";
import { KbSearchBar } from "@/features/kb/KbSearchBar";
import { Pagination } from "@/features/kb/Pagination";

const LIMIT = 20;

export function ChunksTab({
  selectedChunkId,
  onSelectChunk,
  onNavEntity,
  onNavEvent,
}: {
  selectedChunkId: string | null;
  onSelectChunk: (chunkId: string) => void;
  onNavEntity: (normName: string) => void;
  onNavEvent: (eventId: string) => void;
}) {
  const [q, setQ] = useState("");
  const [offset, setOffset] = useState(0);

  const list = useQuery({
    queryKey: ["kb-chunks", q, offset],
    queryFn: () => listChunks({ q: q || undefined, limit: LIMIT, offset }),
  });
  const detail = useQuery({
    queryKey: ["kb-chunk", selectedChunkId],
    queryFn: () => getChunk(selectedChunkId as string),
    enabled: !!selectedChunkId,
  });
  const refEntities = useQuery({
    queryKey: ["kb-chunk-entities", selectedChunkId],
    queryFn: () => listEntities({ chunk_id: selectedChunkId as string, limit: 50 }),
    enabled: !!selectedChunkId,
  });

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div className="space-y-3">
        <KbSearchBar
          placeholder="Tìm trong nội dung chunk…"
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
            <p className="p-4 text-sm text-rose-700">Không tải được danh sách chunk.</p>
          ) : !list.data || list.data.items.length === 0 ? (
            <EmptyState>Không có chunk nào.</EmptyState>
          ) : (
            <ChunkTable
              items={list.data.items}
              selectedId={selectedChunkId}
              onSelect={onSelectChunk}
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
        {!selectedChunkId ? (
          <p className="text-sm text-ink-soft">Chọn một chunk để xem chi tiết.</p>
        ) : detail.isLoading ? (
          <Spinner />
        ) : detail.isError || !detail.data ? (
          <p className="text-sm text-rose-700">Không tải được chi tiết chunk.</p>
        ) : (
          <ChunkDetail
            detail={detail.data}
            referencingEntities={refEntities.data?.items ?? []}
            onNavEntity={onNavEntity}
            onNavEvent={onNavEvent}
          />
        )}
      </div>
    </div>
  );
}
