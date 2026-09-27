import { GitCompare, RotateCcw } from "lucide-react";
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
  return <p className="mt-1 text-[11px] leading-relaxed text-ink-faint">{parts.join(" · ")}</p>;
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
    <div className="space-y-2.5">
      <p className="section-title">Lịch sử phiên bản</p>
      {versions.map((v) => {
        const active = v.version_no === activeVersionNo;
        return (
          <div
            key={v.version_no}
            className={`rounded-lg border p-3 ${
              active ? "border-emerald-600/30 bg-emerald-50/40" : "border-paper-border"
            }`}
          >
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-ink">v{v.version_no}</span>
              <PromptStatusBadge status={v.status} />
              {active && <span className="text-[11px] font-medium text-emerald-700">Hiện hành</span>}
            </div>
            {v.note && <p className="mt-1 text-sm text-ink">{v.note}</p>}
            <AuditLine v={v} />
            <div className="mt-2 flex flex-wrap gap-1">
              {v.status !== "production" && (
                <button
                  onClick={() => onRollback(v.version_no)}
                  disabled={pending}
                  className="btn btn-sm btn-ghost -ml-2 text-brand hover:text-brand-dark"
                >
                  <RotateCcw size={13} />
                  Khôi phục bản này
                </button>
              )}
              <button
                onClick={() => onCompare(v.version_no)}
                className={`btn btn-sm btn-ghost ${v.status === "production" ? "-ml-2" : ""}`}
              >
                <GitCompare size={13} />
                So sánh
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
