import { useCallback, useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { getChunk, listChunks, listEntities } from "@/api/kb";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import { useKbSources } from "@/features/admin/useDocuments";
import { ChunkDetail } from "@/features/kb/ChunkDetail";
import { ChunkTable } from "@/features/kb/ChunkTable";
import { KbSearchBar } from "@/features/kb/KbSearchBar";

const LIMIT = 30;

/** Trang độc lập: tự quản chunk đang chọn (không điều hướng chéo sang tab khác).
 *
 * Lọc theo tài liệu nguồn dùng chung khóa `source_file` với danh mục Tài liệu. Kho chỉ có
 * 1 nguồn -> không hiện ô lọc (vô nghĩa). */
export function ChunksTab() {
  const [q, setQ] = useState("");
  const [sourceFile, setSourceFile] = useState("");
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null);

  const sources = useKbSources();
  const list = useInfiniteQuery({
    queryKey: ["kb-chunks", q, sourceFile],
    queryFn: ({ pageParam }) =>
      listChunks({
        q: q || undefined,
        source_file: sourceFile || undefined,
        limit: LIMIT,
        offset: pageParam,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      const next = lastPage.offset + lastPage.limit;
      return next < lastPage.total ? next : undefined;
    },
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

  const items = list.data?.pages.flatMap((p) => p.items) ?? [];
  const total = list.data?.pages[0]?.total ?? 0;

  // Sentinel cuối danh sách: lọt vào viewport (trong khung cuộn) -> nạp trang kế.
  const { fetchNextPage, hasNextPage, isFetchingNextPage } = list;
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const onIntersect = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      if (entries[0]?.isIntersecting && hasNextPage && !isFetchingNextPage) {
        fetchNextPage();
      }
    },
    [fetchNextPage, hasNextPage, isFetchingNextPage],
  );
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el) return;
    const observer = new IntersectionObserver(onIntersect, {
      root: scrollRef.current,
      rootMargin: "120px",
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [onIntersect]);

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div className="space-y-3">
        <KbSearchBar placeholder="Tìm trong nội dung chunk…" onSearch={setQ}>
          {(sources.data?.length ?? 0) > 1 && (
            <select
              value={sourceFile}
              onChange={(e) => {
                setSourceFile(e.target.value);
                setSelectedChunkId(null);
              }}
              aria-label="Lọc theo tài liệu nguồn"
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

        {list.isLoading ? (
          <div className="rounded-lg border border-paper-border bg-paper-card p-4">
            <Spinner />
          </div>
        ) : list.isError ? (
          <p className="rounded-lg border border-paper-border bg-paper-card p-4 text-sm text-rose-700">
            Không tải được danh sách chunk.
          </p>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-paper-border bg-paper-card">
            <EmptyState>Không có chunk nào.</EmptyState>
          </div>
        ) : (
          <>
            <div
              ref={scrollRef}
              className="max-h-[70vh] overflow-y-auto rounded-lg border border-paper-border bg-paper-card"
            >
              <ChunkTable items={items} selectedId={selectedChunkId} onSelect={setSelectedChunkId} />
              <div ref={sentinelRef} className="h-px" />
              {isFetchingNextPage && (
                <div className="p-3">
                  <Spinner />
                </div>
              )}
            </div>
            <p className="text-center text-xs text-ink-soft">
              Đã tải {items.length} / {total}
              {!hasNextPage && total > 0 && " · hết"}
            </p>
          </>
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
          <ChunkDetail detail={detail.data} referencingEntities={refEntities.data?.items ?? []} />
        )}
      </div>
    </div>
  );
}
