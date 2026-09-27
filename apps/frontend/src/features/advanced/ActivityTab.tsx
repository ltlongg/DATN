import { useState, type FormEvent } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getActivity } from "@/api/activity";
import { Alert } from "@/components/Alert";
import { EmptyState } from "@/components/EmptyState";
import { Pagination } from "@/components/Pagination";
import { Spinner } from "@/components/Spinner";
import type { ActivityLogItem } from "@/types/admin";

const LIMIT = 50;

type SeverityFilter = "" | "ok" | "error";

const dtf = new Intl.DateTimeFormat("vi-VN", { dateStyle: "short", timeStyle: "medium" });

function formatLatency(ms: number | null): string {
  if (ms === null) return "—";
  return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms}ms`;
}

function SeverityBadge({ severity }: { severity: ActivityLogItem["severity"] }) {
  const isError = severity === "error";
  return (
    <span className={`badge ${isError ? "badge-danger" : "badge-success"}`}>
      {severity}
    </span>
  );
}

export function ActivityTab() {
  // `applied` = filter đã bấm "Áp dụng" (tách khỏi input đang gõ để không query mỗi keystroke).
  const [severity, setSeverity] = useState<SeverityFilter>("");
  const [path, setPath] = useState("");
  const [applied, setApplied] = useState<{ severity: SeverityFilter; path: string }>({
    severity: "",
    path: "",
  });
  const [offset, setOffset] = useState(0);

  const query = useQuery({
    queryKey: ["activity", applied, offset],
    queryFn: () =>
      getActivity({
        severity: applied.severity || undefined,
        path: applied.path || undefined,
        limit: LIMIT,
        offset,
      }),
    placeholderData: keepPreviousData,
  });

  function submitFilter(e: FormEvent) {
    e.preventDefault();
    setOffset(0); // đổi filter -> về trang đầu
    setApplied({ severity, path: path.trim() });
  }

  const data = query.data;
  const total = data?.total ?? 0;

  return (
    <div className="space-y-4">
      <form onSubmit={submitFilter} className="card flex flex-wrap items-end gap-3 p-4">
        <label>
          <span className="label text-xs">Mức độ</span>
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as SeverityFilter)}
            className="input h-9 w-40"
          >
            <option value="">Tất cả</option>
            <option value="ok">ok</option>
            <option value="error">error</option>
          </select>
        </label>
        <label className="min-w-[16rem] flex-1 sm:flex-none">
          <span className="label text-xs">Lọc theo path</span>
          <input
            type="text"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="vd: /api/chat/ask"
            className="input h-9 sm:w-72"
          />
        </label>
        <button type="submit" className="btn btn-primary">
          Áp dụng
        </button>
      </form>

      {query.isLoading ? (
        <Spinner />
      ) : query.isError ? (
        <Alert>Không tải được nhật ký hoạt động.</Alert>
      ) : !data || data.items.length === 0 ? (
        <EmptyState>Chưa có hoạt động nào khớp bộ lọc.</EmptyState>
      ) : (
        <div className="card overflow-x-auto">
          <table className="data-table">
            <thead>
              <tr>
                <th>Thời điểm</th>
                <th>Người dùng</th>
                <th>Method</th>
                <th>Path</th>
                <th className="text-right">Status</th>
                <th>Mức độ</th>
                <th className="text-right">Thời lượng</th>
                <th>Lỗi</th>
                <th>Request ID</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((it) => (
                <tr key={it.id}>
                  <td className="whitespace-nowrap tabular-nums text-ink-soft">
                    {dtf.format(new Date(it.created_at))}
                  </td>
                  <td className="text-ink-soft">{it.user_id ?? "—"}</td>
                  <td className="font-mono text-xs font-semibold">{it.method}</td>
                  <td className="font-mono text-xs">{it.path}</td>
                  <td className="text-right tabular-nums text-ink-soft">{it.status_code}</td>
                  <td>
                    <SeverityBadge severity={it.severity} />
                  </td>
                  <td className="whitespace-nowrap text-right tabular-nums text-ink-soft">
                    {formatLatency(it.latency_ms)}
                  </td>
                  <td className={it.error ? "text-rose-700" : "text-ink-faint"}>{it.error ?? "—"}</td>
                  <td
                    className="font-mono text-xs text-ink-soft"
                    title={it.request_id ?? undefined}
                  >
                    {it.request_id ? `${it.request_id.slice(0, 8)}…` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {total > 0 && (
        <Pagination total={total} limit={LIMIT} offset={offset} onChange={setOffset} />
      )}
    </div>
  );
}
