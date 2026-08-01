import { useState } from "react";
import type { ProgressStep, StepState } from "@/types";

/**
 * Bốn trạng thái, KHÔNG phải hai (plan §7.3 mục 1). UI tham chiếu chỉ có chờ/tick-xanh, kể
 * cả khi dòng phụ ghi "chỉ xác minh được 1/2" — với domain lịch sử không chấp nhận được:
 * tick xanh là lời cam kết, không phải hiệu ứng.
 *
 * `pending` sau khi stream đóng đọc là "bước này không chạy" (vd retrieve lỗi nên chưa tới
 * lượt soạn bài), nên để mờ và KHÔNG quay spinner.
 */
const MARK: Record<StepState, { icon: string; className: string; srLabel: string }> = {
  running: { icon: "", className: "text-ink-soft", srLabel: "đang chạy" },
  done: { icon: "✓", className: "text-emerald-600", srLabel: "xong" },
  partial: { icon: "!", className: "text-amber-600", srLabel: "chưa trọn vẹn" },
  pending: { icon: "○", className: "text-ink-soft/40", srLabel: "chưa chạy" },
};

/**
 * Tầng 2: số liệu thô của đúng bước này, trước đây nằm ở DebugPanel (đã xoá 2026-08-01).
 * Render GENERIC theo cặp label/value — thêm bước mới bên agent không phải sửa React.
 */
function InternalsTable({ rows }: { rows: { label: string; value: string }[] }) {
  return (
    <dl className="mt-1.5 space-y-0.5 rounded-md bg-paper-card px-2.5 py-2">
      {rows.map((r, i) => (
        <div key={i} className="flex gap-2 text-xs">
          <dt className="w-36 shrink-0 text-ink-soft">{r.label}</dt>
          {/* break-words: câu truy vấn và chuỗi chunk_id bị loại đều dài, không được đẩy
              ngang cả bong bóng chat. */}
          <dd className="min-w-0 break-words text-ink">{r.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function StepRow({ step, index }: { step: ProgressStep; index: number }) {
  const [open, setOpen] = useState(false);
  const mark = MARK[step.state];
  const dimmed = step.state === "pending";
  // Chỉ admin nhận được `internals` (backend bóc khỏi event `step` khi debug=False), nên
  // sự CÓ MẶT của nó là điều kiện đủ — không cần hỏi role lần nữa ở đây.
  const rows = step.internals ?? [];
  const expandable = rows.length > 0;

  return (
    <li className="flex gap-2.5">
      <span
        className={`mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center text-xs font-semibold ${mark.className}`}
        aria-label={mark.srLabel}
        role="img"
      >
        {step.state === "running" ? (
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-paper-border border-t-brand" />
        ) : (
          mark.icon
        )}
      </span>
      <div className="min-w-0 flex-1">
        {expandable ? (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="flex w-full items-start gap-1.5 text-left hover:text-brand"
          >
            <span className="mt-px text-[10px] text-ink-soft">{open ? "▾" : "▸"}</span>
            <span className="min-w-0">
              <span className={`block text-xs font-medium ${dimmed ? "text-ink-soft" : "text-ink"}`}>
                {index}. {step.label}
              </span>
              {step.detail && <span className="block text-xs text-ink-soft">{step.detail}</span>}
            </span>
          </button>
        ) : (
          <>
            <p className={`text-xs font-medium ${dimmed ? "text-ink-soft" : "text-ink"}`}>
              {index}. {step.label}
            </p>
            {step.detail && <p className="text-xs text-ink-soft">{step.detail}</p>}
          </>
        )}
        {expandable && open && <InternalsTable rows={rows} />}
      </div>
    </li>
  );
}
