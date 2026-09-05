import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { listTimelineCards } from "@/api/timeline";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import { TimelineCard } from "@/features/explore/TimelineCard";
import { shortTime } from "@/features/timeline/timeFormat";
import type { TimelineCardItem } from "@/types/timeline";

const LIMIT = 30;
const VISIBLE_PER_MARK = 3;

interface Mark {
  /** `time_start` thô — dùng làm khoá React và để in nhãn. */
  time: string;
  cards: TimelineCardItem[];
}

/** Gom danh sách phẳng (đã sắp theo thời gian) thành các mốc. */
function buildMarks(items: TimelineCardItem[]): Mark[] {
  const marks: Mark[] = [];

  for (const item of items) {
    const last = marks[marks.length - 1];
    if (last && last.time === item.time_start) last.cards.push(item);
    else marks.push({ time: item.time_start, cards: [item] });
  }
  return marks;
}

export function TimelineSpine() {
  const [expanded, setExpanded] = useState<string | null>(null);
  const [openMarks, setOpenMarks] = useState<Set<string>>(new Set());

  const feed = useInfiniteQuery({
    queryKey: ["timeline-cards"],
    queryFn: ({ pageParam }) => listTimelineCards({ limit: LIMIT, offset: pageParam }),
    initialPageParam: 0,
    getNextPageParam: (lastPage) => {
      const next = lastPage.offset + lastPage.limit;
      return next < lastPage.total ? next : undefined;
    },
  });

  const items = useMemo(
    () => feed.data?.pages.flatMap((p) => p.items) ?? [],
    [feed.data],
  );
  const marks = useMemo(() => buildMarks(items), [items]);
  const total = feed.data?.pages[0]?.total ?? 0;

  // Sentinel cuối feed lọt vào KHUNG CUỘN (không phải cửa sổ) -> nạp trang kế.
  const { fetchNextPage, hasNextPage, isFetchingNextPage } = feed;
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const onIntersect = useCallback(
    (entries: IntersectionObserverEntry[]) => {
      if (entries[0]?.isIntersecting && hasNextPage && !isFetchingNextPage) fetchNextPage();
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

  function toggleMark(time: string) {
    setOpenMarks((prev) => {
      const next = new Set(prev);
      if (!next.delete(time)) next.add(time);
      return next;
    });
  }

  return (
    <div ref={scrollRef} className="h-full overflow-y-auto px-4 py-6 md:px-8">
      <div className="mx-auto max-w-4xl">
        {feed.isLoading ? (
          <Spinner />
        ) : feed.isError ? (
          <p className="text-sm text-rose-700">Không tải được dòng lịch sử.</p>
        ) : marks.length === 0 ? (
          <EmptyState>Chưa có sự kiện nào trong kho.</EmptyState>
        ) : (
          <ol className="space-y-0">
            {marks.map((mark, i) => {
              const isLeft = i % 2 === 0;
              const open = openMarks.has(mark.time);
              const shown = open ? mark.cards : mark.cards.slice(0, VISIBLE_PER_MARK);
              const hidden = mark.cards.length - shown.length;
              return (
                <li
                  key={mark.time}
                  data-side={isLeft ? "left" : "right"}
                  className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 md:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] md:gap-x-6"
                >
                  {/* Cột trục: đường kẻ chạy suốt chiều cao ô -> nối liền giữa các mốc. */}
                  <div className="relative col-start-1 row-start-1 flex w-6 justify-center md:col-start-2">
                    <span aria-hidden className="absolute inset-y-0 w-px bg-paper-border" />
                    <span
                      aria-hidden
                      className="relative mt-1.5 h-2.5 w-2.5 rounded-full border-2 border-brand bg-paper-card"
                    />
                  </div>

                  <div
                    className={`col-start-2 row-start-1 pb-6 ${
                      isLeft ? "md:col-start-1 md:text-right" : "md:col-start-3"
                    }`}
                  >
                    <p className="mb-1.5 text-xs font-semibold tabular-nums text-brand">
                      {shortTime(mark.time)}
                    </p>
                    <div className="space-y-2">
                      {shown.map((c) => (
                        <TimelineCard
                          key={c.event_id}
                          card={c}
                          alignRight={isLeft}
                          expanded={expanded === c.event_id}
                          onToggle={() =>
                            setExpanded(expanded === c.event_id ? null : c.event_id)
                          }
                        />
                      ))}
                      {(hidden > 0 || open) && (
                        <button
                          onClick={() => toggleMark(mark.time)}
                          className="text-xs font-medium text-brand hover:text-brand-dark"
                        >
                          {open ? "thu gọn ▴" : `còn ${hidden} sự kiện ▾`}
                        </button>
                      )}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        )}

        <div ref={sentinelRef} className="h-px" />
        {isFetchingNextPage && (
          <div className="py-4">
            <Spinner />
          </div>
        )}

        <footer className="border-t border-paper-border pt-3 text-center text-xs text-ink-soft">
          Đã hiện {items.length} / {total} sự kiện. Trang này chỉ hiện sự kiện đã xác định
          được thời gian.
        </footer>
      </div>
    </div>
  );
}
