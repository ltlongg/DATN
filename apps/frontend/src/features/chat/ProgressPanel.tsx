import { useEffect, useState } from "react";
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
    <div className="mb-3 rounded-lg border border-paper-border bg-paper px-3 py-2">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 text-xs text-ink-soft hover:text-brand"
      >
        <span>{summary}</span>
        <span>{open ? "Ẩn tiến trình" : "Xem tiến trình"}</span>
      </button>

      {open && (
        <ol className="mt-2 space-y-1.5">
          {steps.map((step, i) => (
            <StepRow key={step.id} step={step} index={i + 1} />
          ))}
        </ol>
      )}
    </div>
  );
}
