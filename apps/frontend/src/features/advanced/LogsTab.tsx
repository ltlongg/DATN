import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getConversationLog, getQualitySummary, listConversationLogs } from "@/api/logs";
import { EmptyState } from "@/components/EmptyState";
import { Modal } from "@/components/Modal";
import { Spinner } from "@/components/Spinner";
import { ConversationLogDetail } from "@/features/advanced/ConversationLogDetail";
import { ConversationLogTable } from "@/features/advanced/ConversationLogTable";
import { LogsFilterBar, type LogsFilterValue } from "@/features/advanced/LogsFilterBar";
import { QualitySummaryCard } from "@/features/advanced/QualitySummaryCard";
import { Pagination } from "@/features/kb/Pagination";

const LIMIT = 20;
const EMPTY: LogsFilterValue = { user_email: "", from_date: "", to_date: "" };

export function LogsTab() {
  const [filter, setFilter] = useState<LogsFilterValue>(EMPTY);
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);

  const range = { from_date: filter.from_date || undefined, to_date: filter.to_date || undefined };

  const summary = useQuery({
    queryKey: ["adm-quality", range],
    queryFn: () => getQualitySummary(range),
  });
  const logs = useQuery({
    queryKey: ["adm-logs", filter, offset],
    queryFn: () =>
      listConversationLogs({
        user_email: filter.user_email || undefined,
        ...range,
        limit: LIMIT,
        offset,
      }),
  });
  const detail = useQuery({
    queryKey: ["adm-log", openId],
    queryFn: () => getConversationLog(openId as string),
    enabled: !!openId,
  });

  return (
    <div className="space-y-4">
      {summary.data && <QualitySummaryCard summary={summary.data} />}

      <LogsFilterBar
        onApply={(v) => {
          setFilter(v);
          setOffset(0);
        }}
      />

      <div className="rounded-lg border border-paper-border bg-paper-card p-3">
        {logs.isLoading ? (
          <Spinner />
        ) : logs.isError ? (
          <p className="text-sm text-rose-700">Không tải được danh sách hội thoại.</p>
        ) : !logs.data || logs.data.items.length === 0 ? (
          <EmptyState>Không có hội thoại nào khớp bộ lọc.</EmptyState>
        ) : (
          <ConversationLogTable items={logs.data.items} onOpen={setOpenId} />
        )}
      </div>
      {logs.data && (
        <Pagination total={logs.data.total} limit={LIMIT} offset={offset} onChange={setOffset} />
      )}

      <Modal open={openId !== null} onOpenChange={(o) => !o && setOpenId(null)} title="Chi tiết hội thoại">
        {detail.isLoading ? (
          <Spinner />
        ) : detail.data ? (
          <ConversationLogDetail detail={detail.data} />
        ) : (
          <p className="text-sm text-rose-700">Không tải được hội thoại.</p>
        )}
      </Modal>
    </div>
  );
}
