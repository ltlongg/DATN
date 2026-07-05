import { useCallback, useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { getEntity, listEntities } from "@/api/kb";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import { EntityDetail } from "@/features/kb/EntityDetail";
import { EntityTable } from "@/features/kb/EntityTable";
import { KbSearchBar } from "@/features/kb/KbSearchBar";

const LIMIT = 30;

/** 7 loại entity chuẩn (khớp prompts/graph_extract.py) — filter facet. */
const ENTITY_TYPES = [
  "Nhân vật",
  "Tổ chức",
  "Địa điểm",
  "Sự kiện",
  "Văn kiện",
  "Chủ trương",
  "Chức danh",
] as const;

/** Trang độc lập: tự quản thực thể đang chọn. `onSelectEntity` chỉ đổi selection NỘI BỘ
 * (click node ego-graph mở thực thể khác trong cùng trang), không nhảy sang tab khác. */
export function GraphTab() {
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [selectedNorm, setSelectedNorm] = useState<string | null>(null);

  const list = useInfiniteQuery({
    queryKey: ["kb-entities", q, type],
    queryFn: ({ pageParam }) =>
      listEntities({ q: q || undefined, type: type || undefined, limit: LIMIT, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      const next = lastPage.offset + lastPage.limit;
      return next < lastPage.total ? next : undefined;
    },
  });
  const detail = useQuery({
    queryKey: ["kb-entity", selectedNorm],
    queryFn: () => getEntity(selectedNorm as string),
    enabled: !!selectedNorm,
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
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
      <div className="space-y-3">
        <KbSearchBar
          placeholder="Tìm thực thể theo tên…"
          onSearch={setQ}
        >
          <select
            value={type}
            onChange={(e) => setType(e.target.value)}
            aria-label="Lọc theo loại thực thể"
            className="rounded-md border border-paper-border px-2 py-1.5 text-sm outline-none focus:border-brand"
          >
            <option value="">Tất cả loại</option>
            {ENTITY_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </KbSearchBar>

        {list.isLoading ? (
          <div className="rounded-lg border border-paper-border bg-paper-card p-4">
            <Spinner />
          </div>
        ) : list.isError ? (
          <p className="rounded-lg border border-paper-border bg-paper-card p-4 text-sm text-rose-700">
            Không tải được danh sách thực thể.
          </p>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-paper-border bg-paper-card">
            <EmptyState>Không có thực thể khớp bộ lọc.</EmptyState>
          </div>
        ) : (
          <>
            <div
              ref={scrollRef}
              className="max-h-[70vh] overflow-y-auto rounded-lg border border-paper-border bg-paper-card"
            >
              <EntityTable items={items} selectedNorm={selectedNorm} onSelect={setSelectedNorm} />
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
        {!selectedNorm ? (
          <p className="text-sm text-ink-soft">Chọn một thực thể để xem ego-graph.</p>
        ) : detail.isLoading ? (
          <Spinner />
        ) : detail.isError || !detail.data ? (
          <p className="text-sm text-rose-700">Không tải được chi tiết thực thể.</p>
        ) : (
          <EntityDetail detail={detail.data} onSelectEntity={setSelectedNorm} />
        )}
      </div>
    </div>
  );
}
