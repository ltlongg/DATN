import { useState, type FormEvent } from "react";

export interface CostRangeValue {
  from_date: string;
  to_date: string;
}

/** Ngày dạng YYYY-MM-DD, mặc định 7 ngày gần nhất. */
export function defaultRange(): CostRangeValue {
  const to = new Date();
  const from = new Date();
  from.setDate(to.getDate() - 6);
  const iso = (d: Date) => d.toISOString().slice(0, 10);
  return { from_date: iso(from), to_date: iso(to) };
}

export function CostFilterBar({
  initial,
  onApply,
}: {
  initial: CostRangeValue;
  onApply: (v: CostRangeValue) => void;
}) {
  const [from, setFrom] = useState(initial.from_date);
  const [to, setTo] = useState(initial.to_date);

  function submit(e: FormEvent) {
    e.preventDefault();
    onApply({ from_date: from, to_date: to });
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <label className="text-sm">
        <span className="block text-xs text-ink-soft">Từ ngày</span>
        <input
          type="date"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          className="rounded-md border border-paper-border px-2 py-1.5 outline-none focus:border-brand"
        />
      </label>
      <label className="text-sm">
        <span className="block text-xs text-ink-soft">Đến ngày</span>
        <input
          type="date"
          value={to}
          onChange={(e) => setTo(e.target.value)}
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
  );
}
