import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getConversationLog,
  getConversationTokens,
  getQualitySummary,
  getTokenSummary,
  listConversationLogs,
} from "@/api/logs";
import { Alert } from "@/components/Alert";
import { EmptyState } from "@/components/EmptyState";
import { Spinner } from "@/components/Spinner";
import { ConversationDetailPanel } from "@/features/advanced/ConversationDetailPanel";
import { ConversationReplay } from "@/features/advanced/ConversationReplay";
import { ConversationSessionList } from "@/features/advanced/ConversationSessionList";
import { LogsFilterBar, type LogsFilterValue } from "@/features/advanced/LogsFilterBar";
import { QualitySummaryCard } from "@/features/advanced/QualitySummaryCard";
import { TokenSummaryCard } from "@/features/advanced/TokenSummaryCard";
import { Pagination } from "@/components/Pagination";
import type { MessageTokens } from "@/types/admin";

const LIMIT = 20;
const EMPTY: LogsFilterValue = {
  user_anon_id: "",
  flagged_only: false,
  from_date: "",
  to_date: "",
};

function SummarySection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="space-y-2.5">
      <p className="section-title">{title}</p>
      {children}
    </div>
  );
}

export function LogsTab() {
  const [filter, setFilter] = useState<LogsFilterValue>(EMPTY);
  const [offset, setOffset] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const range = { from_date: filter.from_date || undefined, to_date: filter.to_date || undefined };

  const summary = useQuery({
    queryKey: ["adm-quality", range],
    queryFn: () => getQualitySummary(range),
  });
  const tokenSummary = useQuery({
    queryKey: ["adm-token-summary", range],
    queryFn: () => getTokenSummary(range),
  });
  const logs = useQuery({
    queryKey: ["adm-logs", filter, offset],
    queryFn: () =>
      listConversationLogs({
        user_anon_id: filter.user_anon_id || undefined,
        flagged_only: filter.flagged_only || undefined,
        ...range,
        limit: LIMIT,
        offset,
      }),
  });
  const detail = useQuery({
    queryKey: ["adm-log", selectedId],
    queryFn: () => getConversationLog(selectedId as string),
    enabled: !!selectedId,
  });
  const detailTokens = useQuery({
    queryKey: ["adm-log-tokens", selectedId],
    queryFn: () => getConversationTokens(selectedId as string),
    enabled: !!selectedId,
  });

  // Auto-chọn phiên đầu khi danh sách đổi (và phiên đang chọn không còn trong trang hiện tại).
  const items = logs.data?.items;
  useEffect(() => {
    if (items && items.length > 0 && !items.some((c) => c.id === selectedId)) {
      setSelectedId(items[0].id);
    }
  }, [items, selectedId]);

  const tokensByConv = useMemo(
    () =>
      new Map(
        (tokenSummary.data?.by_conversation ?? []).map((c) => [c.conversation_id, c.total_tokens]),
      ),
    [tokenSummary.data],
  );
  const tokensByMessage = useMemo(
    () => new Map<string, MessageTokens>((detailTokens.data ?? []).map((t) => [t.message_id, t])),
    [detailTokens.data],
  );

  return (
    <div className="space-y-6">
      {summary.data && (
        <SummarySection title="Chất lượng câu trả lời">
          <QualitySummaryCard summary={summary.data} />
        </SummarySection>
      )}
      {tokenSummary.data && (
        <SummarySection title="Token (đã gắn hội thoại)">
          <TokenSummaryCard overall={tokenSummary.data.overall} />
        </SummarySection>
      )}

      <LogsFilterBar
        onApply={(v) => {
          setFilter(v);
          setOffset(0);
          setSelectedId(null);
        }}
      />

      {logs.isLoading ? (
        <Spinner />
      ) : logs.isError ? (
        <Alert>Không tải được danh sách hội thoại.</Alert>
      ) : !logs.data || logs.data.items.length === 0 ? (
        <EmptyState>Không có hội thoại nào khớp bộ lọc.</EmptyState>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,2fr)_minmax(0,1.1fr)]">
          {/* Trái: danh sách phiên + phân trang */}
          <div className="space-y-3">
            <div className="card p-2">
              <p className="section-title px-2 pb-2 pt-1">{logs.data.total} phiên</p>
              <ConversationSessionList
                items={logs.data.items}
                selectedId={selectedId}
                tokensByConv={tokensByConv}
                onSelect={setSelectedId}
              />
            </div>
            <Pagination
              total={logs.data.total}
              limit={LIMIT}
              offset={offset}
              onChange={(o) => {
                setOffset(o);
                setSelectedId(null);
              }}
            />
          </div>

          {/* Giữa: replay hội thoại */}
          <div className="card min-h-[24rem] p-5">
            {detail.isLoading ? (
              <Spinner />
            ) : detail.data ? (
              <ConversationReplay detail={detail.data} />
            ) : (
              <p className="text-sm text-ink-soft">Chọn một phiên để xem lại hội thoại.</p>
            )}
          </div>

          {/* Phải: panel chất lượng / token */}
          <div className="card min-h-[24rem] p-5">
            {detail.data ? (
              <ConversationDetailPanel detail={detail.data} tokensByMessage={tokensByMessage} />
            ) : (
              <p className="text-sm text-ink-faint">—</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
