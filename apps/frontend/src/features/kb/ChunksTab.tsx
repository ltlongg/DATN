import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getChunk, listChunks, listEntities } from "@/api/kb";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import { useKbSources } from "@/features/admin/useDocuments";
import { ChunkDetail } from "@/features/kb/ChunkDetail";
import { ChunkTable } from "@/features/kb/ChunkTable";
import { KbSearchBar } from "@/features/kb/KbSearchBar";
import { Pagination } from "@/features/kb/Pagination";

const LIMIT = 20;

/** Trang độc lập: tự quản chunk đang chọn (không điều hướng chéo sang tab khác).
 *
 * Lọc theo tài liệu nguồn dùng chung khóa `source_file` với danh mục Tài liệu. Kho chỉ có
 * 1 nguồn -> không hiện ô lọc (vô nghĩa). */
export function ChunksTab() {
  const [q, setQ] = useState("");
  const [sourceFile, setSourceFile] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null);

  const sources = useKbSources();
  const list = useQuery({
    queryKey: ["kb-chunks", q, sourceFile, offset],
    queryFn: () =>
      listChunks({
        q: q || undefined,
        source_file: sourceFile || undefined,
        limit: LIMIT,
        offset,
      }),
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
        >
          {(sources.data?.length ?? 0) > 1 && (
            <select
              value={sourceFile}
              onChange={(e) => {
                setSourceFile(e.target.value);
                setOffset(0);
                setSelectedChunkId(null);
              }}
              className="rounded-md border border-paper-border px-2 py-1.5 text-sm outline-none focus:border-brand"
            >
              <option value="">Mọi tài liệu</option>
              {sources.data?.map((s) => (
                <option key={s.source_file} value={s.source_file}>
                  {s.source_file}
                </option>
              ))}
            </select>
          )}
        </KbSearchBar>
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
              onSelect={setSelectedChunkId}
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
          />
        )}
      </div>
    </div>
  );
}
