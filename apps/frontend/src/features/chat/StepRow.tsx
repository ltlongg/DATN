import { useState } from "react";
import {
  AlertTriangle,
  Check,
  ChevronRight,
  Circle,
  Minus,
  type LucideIcon,
} from "lucide-react";
import type { ProgressStep, StepState } from "@/types";

/**
 * Năm trạng thái, KHÔNG phải hai (plan §7.3 mục 1). UI tham chiếu chỉ có chờ/tick-xanh, kể
 * cả khi dòng phụ ghi "chỉ xác minh được 1/2" — với domain lịch sử không chấp nhận được:
 * tick xanh là lời cam kết, không phải hiệu ứng.
 *
 * `pending` sau khi stream đóng đọc là "bước này không chạy" (vd retrieve lỗi nên chưa tới
 * lượt soạn bài), nên để mờ và KHÔNG quay spinner. `skipped` mạnh hơn một bậc: hệ thống đã
 * chạy tới đây rồi CHỦ ĐỘNG bỏ (không trích được mắt xích thì tra tiếp cũng bằng thừa) —
 * gạch ngang để đọc ra ngay là có bước đã bị cắt khỏi kế hoạch ban đầu.
 */
const MARK: Record<StepState, { icon: LucideIcon | null; className: string; srLabel: string }> = {
  running: { icon: null, className: "text-ink-soft", srLabel: "đang chạy" },
  done: { icon: Check, className: "text-emerald-600", srLabel: "xong" },
  partial: { icon: AlertTriangle, className: "text-amber-600", srLabel: "chưa trọn vẹn" },
  skipped: { icon: Minus, className: "text-ink-faint", srLabel: "đã bỏ qua" },
  pending: { icon: Circle, className: "text-ink-faint/60", srLabel: "chưa chạy" },
};

/**
 * Tầng 2: số liệu thô của đúng bước này, trước đây nằm ở DebugPanel (đã xoá 2026-08-01).
 * Render GENERIC theo cặp label/value — thêm bước mới bên agent không phải sửa React.
 */
function InternalsTable({ rows }: { rows: { label: string; value: string }[] }) {
  return (
    <dl className="mt-2 space-y-1 rounded-lg border border-paper-border bg-paper-card px-3 py-2">
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
  const Icon = mark.icon;
  const labelClass =
    step.state === "skipped"
      ? "text-ink-soft line-through"
      : step.state === "pending"
        ? "text-ink-soft"
        : "text-ink";
  // Chỉ admin nhận được `internals` (backend bóc khỏi event `step` khi debug=False), nên
  // sự CÓ MẶT của nó là điều kiện đủ — không cần hỏi role lần nữa ở đây.
  const rows = step.internals ?? [];
  const expandable = rows.length > 0;

  return (
    <li className="flex gap-2.5">
      <span
        className={`mt-px flex h-4 w-4 shrink-0 items-center justify-center ${mark.className}`}
        aria-label={mark.srLabel}
        role="img"
      >
        {Icon ? (
          <Icon size={step.state === "pending" ? 10 : 14} strokeWidth={2.5} aria-hidden />
        ) : (
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-paper-border border-t-brand" />
        )}
      </span>
      <div className="min-w-0 flex-1">
        {expandable ? (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            aria-expanded={open}
            className="group flex w-full items-start gap-1 text-left"
          >
            <ChevronRight
              size={14}
              className={`mt-px shrink-0 text-ink-faint transition-transform group-hover:text-brand ${
                open ? "rotate-90" : ""
              }`}
              aria-hidden
            />
            <span className="min-w-0">
              <span className={`block text-xs font-medium ${labelClass}`}>
                {index}. {step.label}
              </span>
              {step.detail && <span className="block text-xs text-ink-soft">{step.detail}</span>}
            </span>
          </button>
        ) : (
          <>
            <p className={`text-xs font-medium ${labelClass}`}>
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
