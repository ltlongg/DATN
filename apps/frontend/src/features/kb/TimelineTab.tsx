import { useCallback, useEffect, useRef, useState } from "react";
import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { getEvent, listEvents } from "@/api/kb";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import { EventDetail } from "@/features/kb/EventDetail";
import { EventTable } from "@/features/kb/EventTable";
import { KbSearchBar } from "@/features/kb/KbSearchBar";

const LIMIT = 30;

/** Trang độc lập: tự quản sự kiện đang chọn (không điều hướng chéo sang tab khác). */
export function TimelineTab() {
  const [q, setQ] = useState("");
  const [confidence, setConfidence] = useState("");
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  const list = useInfiniteQuery({
    queryKey: ["kb-events", q, confidence],
    queryFn: ({ pageParam }) =>
      listEvents({
        q: q || undefined,
        confidence: confidence || undefined,
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
    queryKey: ["kb-event", selectedEventId],
    queryFn: () => getEvent(selectedEventId as string),
    enabled: !!selectedEventId,
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
        <KbSearchBar placeholder="Tìm sự kiện theo nhãn/summary…" onSearch={setQ}>
          <select
            value={confidence}
            onChange={(e) => setConfidence(e.target.value)}
            aria-label="Lọc theo độ tin cậy"
            className="rounded-md border border-paper-border px-2 py-1.5 text-sm outline-none focus:border-brand"
          >
            <option value="">Mọi độ tin cậy</option>
            <option value="cao">cao</option>
            <option value="vừa">vừa</option>
            <option value="thấp">thấp</option>
          </select>
        </KbSearchBar>

        {list.isLoading ? (
          <div className="rounded-lg border border-paper-border bg-paper-card p-4">
            <Spinner />
          </div>
        ) : list.isError ? (
          <p className="rounded-lg border border-paper-border bg-paper-card p-4 text-sm text-rose-700">
            Không tải được danh sách sự kiện.
          </p>
        ) : items.length === 0 ? (
          <div className="rounded-lg border border-paper-border bg-paper-card">
            <EmptyState>Không có sự kiện nào.</EmptyState>
          </div>
        ) : (
          <>
            <div
              ref={scrollRef}
              className="max-h-[70vh] overflow-y-auto rounded-lg border border-paper-border bg-paper-card"
            >
              <EventTable items={items} selectedId={selectedEventId} onSelect={setSelectedEventId} />
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
        {!selectedEventId ? (
          <p className="text-sm text-ink-soft">Chọn một sự kiện để xem chi tiết.</p>
        ) : detail.isLoading ? (
          <Spinner />
        ) : detail.isError || !detail.data ? (
          <p className="text-sm text-rose-700">Không tải được chi tiết sự kiện.</p>
        ) : (
          <EventDetail detail={detail.data} />
        )}
      </div>
    </div>
  );
}
