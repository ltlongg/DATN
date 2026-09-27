import { useEffect, useState } from "react";
import { ChevronDown, ListChecks } from "lucide-react";
import { StepRow } from "@/features/chat/StepRow";
import { formatDuration } from "@/lib/format";
import type { ProgressStep } from "@/types";

/** Bước đã có kết — `pending` không tính (nó nghĩa là chưa/không chạy). */
function finishedCount(steps: ProgressStep[]): number {
  return steps.filter((s) => s.state === "done" || s.state === "partial").length;
}

/**
 * Panel tiến trình (B3, plan §7.3) — nằm TRONG bong bóng assistant, phía trên câu trả lời.
 * Mở khi đang chạy, tự gập thành một dòng khi xong, click mở lại.
 *
 * Thời gian đo CLIENT-SIDE từ lúc mở stream (`startedAt`), nên message nạp lại từ DB không
 * có (`startedAt === null`) — V1 cố ý chấp nhận: reload thấy đủ bước + kết quả, không có
 * thời gian. Đừng tưởng là bug. Con số `ttft_ms` dưới câu trả lời là chỉ số KHÁC (backend
 * đo tới token đầu tiên), không thay thế được cái này.
 */
export function ProgressPanel({
  steps,
  startedAt,
  streaming,
}: {
  steps: ProgressStep[];
  startedAt: number | null;
  streaming: boolean;
}) {
  const [open, setOpen] = useState(true);
  const [autoCollapsed, setAutoCollapsed] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const [frozenMs, setFrozenMs] = useState<number | null>(null);

  // Đồng hồ chạy chỉ trong lúc stream mở; 100ms đủ mượt cho một con số 1 chữ số thập phân.
  useEffect(() => {
    if (!streaming || startedAt === null) return;
    const timer = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(timer);
  }, [streaming, startedAt]);

  // Chốt thời gian đúng lúc stream đóng, không để nó nhích tiếp theo `now`.
  useEffect(() => {
    if (!streaming && startedAt !== null && frozenMs === null) {
      setFrozenMs(Date.now() - startedAt);
    }
  }, [streaming, startedAt, frozenMs]);

  // Xong thì gập — nhưng chỉ MỘT lần, để người dùng mở lại rồi không bị đóng sập.
  useEffect(() => {
    if (!streaming && !autoCollapsed) {
      setOpen(false);
      setAutoCollapsed(true);
    }
  }, [streaming, autoCollapsed]);

  if (steps.length === 0) return null;

  const elapsedMs = startedAt === null ? null : (frozenMs ?? now - startedAt);
  const summary = [
    streaming ? "Đang xử lý" : "Đã hoàn thành",
    `${finishedCount(steps)}/${steps.length} bước`,
    ...(elapsedMs === null ? [] : [formatDuration(elapsedMs)]),
  ].join(" · ");

  return (
    <div className="mb-4 rounded-xl border border-paper-border bg-paper/70">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 rounded-xl px-3.5 py-2.5 text-xs text-ink-soft transition-colors hover:text-ink"
      >
        <span className="flex items-center gap-2">
          {streaming ? (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-paper-border border-t-brand" />
          ) : (
            <ListChecks size={14} className="text-ink-faint" aria-hidden />
          )}
          <span>{summary}</span>
        </span>
        <span className="flex items-center gap-1">
          <span>{open ? "Ẩn tiến trình" : "Xem tiến trình"}</span>
          <ChevronDown
            size={14}
            className={`transition-transform ${open ? "rotate-180" : ""}`}
            aria-hidden
          />
        </span>
      </button>

      {open && (
        <ol className="space-y-2 border-t border-paper-border px-3.5 py-3">
          {steps.map((step, i) => (
            <StepRow key={step.id} step={step} index={i + 1} />
          ))}
        </ol>
      )}
    </div>
  );
}
