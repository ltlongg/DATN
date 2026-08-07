import { formatDateTime } from "@/lib/format";
import { PromptStatusBadge } from "@/features/prompts/PromptStatusBadge";
import type { PromptVersionMeta } from "@/types/prompt";

function AuditLine({ v }: { v: PromptVersionMeta }) {
  const parts: string[] = [];
  if (v.created_by) parts.push(`tạo bởi ${v.created_by}`);
  if (v.promoted_by && v.promoted_at) {
    parts.push(`đẩy bởi ${v.promoted_by} lúc ${formatDateTime(v.promoted_at)}`);
  }
  if (parts.length === 0) return null;
  return <p className="mt-0.5 text-[11px] text-ink-soft">{parts.join(" · ")}</p>;
}

/** Cột phải: lịch sử version + khôi phục bản cũ + so sánh với bản production hiện hành. */
export function VersionHistory({
  versions,
  activeVersionNo,
  pending,
  onRollback,
  onCompare,
}: {
  versions: PromptVersionMeta[];
  activeVersionNo: number | null;
  pending: boolean;
  onRollback: (versionNo: number) => void;
  onCompare: (versionNo: number) => void;
}) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">Lịch sử phiên bản</p>
      {versions.map((v) => (
        <div key={v.version_no} className="rounded-md border border-paper-border p-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-medium text-ink">v{v.version_no}</span>
            <PromptStatusBadge status={v.status} />
            {v.version_no === activeVersionNo && (
              <span className="text-[11px] font-medium text-green-700">Hiện hành</span>
            )}
          </div>
          {v.note && <p className="mt-0.5 text-xs text-ink">{v.note}</p>}
          <AuditLine v={v} />
          <div className="mt-1.5 flex gap-3 text-xs">
            {v.status !== "production" && (
              <button
                onClick={() => onRollback(v.version_no)}
                disabled={pending}
                className="text-brand hover:underline disabled:opacity-50"
              >
                Khôi phục bản này
              </button>
            )}
            <button onClick={() => onCompare(v.version_no)} className="text-ink-soft hover:text-ink">
              So sánh
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
