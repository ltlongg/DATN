import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getEvent, listEvents } from "@/api/kb";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import { EventDetail } from "@/features/kb/EventDetail";
import { EventTable } from "@/features/kb/EventTable";
import { KbSearchBar } from "@/features/kb/KbSearchBar";
import { Pagination } from "@/features/kb/Pagination";

const LIMIT = 20;

/** Trang độc lập: tự quản sự kiện đang chọn (không điều hướng chéo sang tab khác). */
export function TimelineTab() {
  const [q, setQ] = useState("");
  const [confidence, setConfidence] = useState("");
  const [offset, setOffset] = useState(0);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  const list = useQuery({
    queryKey: ["kb-events", q, confidence, offset],
    queryFn: () =>
      listEvents({ q: q || undefined, confidence: confidence || undefined, limit: LIMIT, offset }),
  });
  const detail = useQuery({
    queryKey: ["kb-event", selectedEventId],
    queryFn: () => getEvent(selectedEventId as string),
    enabled: !!selectedEventId,
  });

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <div className="space-y-3">
        <KbSearchBar
          placeholder="Tìm sự kiện theo nhãn/summary…"
          onSearch={(v) => {
            setQ(v);
            setOffset(0);
          }}
        >
          <select
            value={confidence}
            onChange={(e) => {
              setConfidence(e.target.value);
              setOffset(0);
            }}
            className="rounded-md border border-paper-border px-2 py-1.5 text-sm outline-none focus:border-brand"
          >
            <option value="">Mọi độ tin cậy</option>
            <option value="cao">cao</option>
            <option value="vừa">vừa</option>
            <option value="thấp">thấp</option>
          </select>
        </KbSearchBar>
        <div className="rounded-lg border border-paper-border bg-paper-card">
          {list.isLoading ? (
            <div className="p-4">
              <Spinner />
            </div>
          ) : list.isError ? (
            <p className="p-4 text-sm text-rose-700">Không tải được danh sách sự kiện.</p>
          ) : !list.data || list.data.items.length === 0 ? (
            <EmptyState>Không có sự kiện nào.</EmptyState>
          ) : (
            <EventTable
              items={list.data.items}
              selectedId={selectedEventId}
              onSelect={setSelectedEventId}
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
