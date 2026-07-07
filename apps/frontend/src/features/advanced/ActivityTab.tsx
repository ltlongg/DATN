import { useState, type FormEvent } from "react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { getActivity } from "@/api/activity";
import { EmptyState } from "@/components/EmptyState";
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
    <span
      className={`rounded px-1.5 py-0.5 text-xs font-medium ${
        isError ? "bg-rose-100 text-rose-700" : "bg-emerald-100 text-emerald-700"
      }`}
    >
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
      <form onSubmit={submitFilter} className="flex flex-wrap items-end gap-2">
        <label className="text-sm">
          <span className="block text-xs text-ink-soft">Mức độ</span>
          <select
            value={severity}
            onChange={(e) => setSeverity(e.target.value as SeverityFilter)}
            className="rounded-md border border-paper-border px-2 py-1.5 outline-none focus:border-brand"
          >
            <option value="">Tất cả</option>
            <option value="ok">ok</option>
            <option value="error">error</option>
          </select>
        </label>
        <label className="text-sm">
          <span className="block text-xs text-ink-soft">Lọc theo path</span>
          <input
            type="text"
            value={path}
            onChange={(e) => setPath(e.target.value)}
            placeholder="vd: /api/chat/ask"
            className="rounded-md border border-paper-border px-2 py-1.5 outline-none focus:border-brand"
          />
        </label>
        <button
          type="submit"
          className="rounded-md bg-brand px-3 py-1.5 text-sm text-brand-fg hover:bg-brand-dark"
        >
          Áp dụng
        </button>
      </form>

      {query.isLoading ? (
        <Spinner />
      ) : query.isError ? (
        <p className="text-sm text-rose-700">Không tải được nhật ký hoạt động.</p>
      ) : !data || data.items.length === 0 ? (
        <EmptyState>Chưa có hoạt động nào khớp bộ lọc.</EmptyState>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-paper-border bg-paper-card">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="border-b border-paper-border text-left text-ink-soft">
                <th className="px-3 py-2 font-medium">Thời điểm</th>
                <th className="px-3 py-2 font-medium">Người dùng</th>
                <th className="px-3 py-2 font-medium">Method</th>
                <th className="px-3 py-2 font-medium">Path</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Mức độ</th>
                <th className="px-3 py-2 font-medium">Thời lượng</th>
                <th className="px-3 py-2 font-medium">Lỗi</th>
                <th className="px-3 py-2 font-medium">Request ID</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((it) => (
                <tr key={it.id} className="border-b border-paper-border/60 align-top">
                  <td className="whitespace-nowrap px-3 py-2 text-ink-soft">
                    {dtf.format(new Date(it.created_at))}
                  </td>
                  <td className="px-3 py-2 text-ink-soft">{it.user_id ?? "—"}</td>
                  <td className="px-3 py-2 font-medium text-ink">{it.method}</td>
                  <td className="px-3 py-2 font-mono text-xs text-ink">{it.path}</td>
                  <td className="px-3 py-2 text-ink-soft">{it.status_code}</td>
                  <td className="px-3 py-2">
                    <SeverityBadge severity={it.severity} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2 text-ink-soft">
                    {formatLatency(it.latency_ms)}
                  </td>
                  <td className="px-3 py-2 text-rose-700">{it.error ?? "—"}</td>
                  <td
                    className="px-3 py-2 font-mono text-xs text-ink-soft"
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
        <div className="flex items-center justify-between text-sm text-ink-soft">
          <span>
            {offset + 1}–{Math.min(offset + LIMIT, total)} / {total}
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              disabled={offset === 0}
              onClick={() => setOffset((o) => Math.max(0, o - LIMIT))}
              className="rounded-md border border-paper-border px-3 py-1 disabled:opacity-40"
            >
              Trước
            </button>
            <button
              type="button"
              disabled={offset + LIMIT >= total}
              onClick={() => setOffset((o) => o + LIMIT)}
              className="rounded-md border border-paper-border px-3 py-1 disabled:opacity-40"
            >
              Sau
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
