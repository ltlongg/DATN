import { useState, type FormEvent } from "react";

const BTN = "rounded-md border border-paper-border px-2 py-1 disabled:opacity-40 hover:bg-paper";

/** Phân trang offset/limit: nhảy đầu/cuối + tiến/lùi + ô "tới trang" (bỏ Trước/Sau đơn điệu). */
export function Pagination({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number;
  limit: number;
  offset: number;
  onChange: (offset: number) => void;
}) {
  const [jump, setJump] = useState("");

  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);
  const pageCount = Math.max(1, Math.ceil(total / limit));
  const page = Math.floor(offset / limit) + 1;
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  function goPage(p: number) {
    const clamped = Math.min(Math.max(1, p), pageCount);
    onChange((clamped - 1) * limit);
  }

  function submitJump(e: FormEvent) {
    e.preventDefault();
    const n = Number.parseInt(jump, 10);
    if (!Number.isNaN(n)) goPage(n);
    setJump("");
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-ink-soft">
      <span>
        {from}–{to} / {total}
      </span>
      <div className="flex items-center gap-1">
        <button disabled={!canPrev} onClick={() => goPage(1)} className={BTN} aria-label="Trang đầu">
          «
        </button>
        <button disabled={!canPrev} onClick={() => goPage(page - 1)} className={BTN}>
          Trước
        </button>
        <span className="px-1 tabular-nums">
          {page} / {pageCount}
        </span>
        <button disabled={!canNext} onClick={() => goPage(page + 1)} className={BTN}>
          Sau
        </button>
        <button disabled={!canNext} onClick={() => goPage(pageCount)} className={BTN} aria-label="Trang cuối">
          »
        </button>
        {pageCount > 2 && (
          <form onSubmit={submitJump} className="ml-1 flex items-center gap-1">
            <input
              value={jump}
              onChange={(e) => setJump(e.target.value)}
              inputMode="numeric"
              placeholder="Tới…"
              aria-label="Tới trang"
              className="w-16 rounded-md border border-paper-border px-2 py-1 text-sm outline-none focus:border-brand"
            />
          </form>
        )}
      </div>
    </div>
  );
}
