/** Phân trang đơn giản theo offset/limit + tổng count. */
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
  const from = total === 0 ? 0 : offset + 1;
  const to = Math.min(offset + limit, total);
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  return (
    <div className="flex items-center justify-between text-sm text-ink-soft">
      <span>
        {from}–{to} / {total}
      </span>
      <div className="flex gap-2">
        <button
          disabled={!canPrev}
          onClick={() => onChange(Math.max(0, offset - limit))}
          className="rounded-md border border-paper-border px-2 py-1 disabled:opacity-40"
        >
          Trước
        </button>
        <button
          disabled={!canNext}
          onClick={() => onChange(offset + limit)}
          className="rounded-md border border-paper-border px-2 py-1 disabled:opacity-40"
        >
          Sau
        </button>
      </div>
    </div>
  );
}
