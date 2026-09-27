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
    <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
      <label>
        <span className="label text-xs">Từ ngày</span>
        <input
          type="date"
          value={from}
          onChange={(e) => setFrom(e.target.value)}
          className="input h-9 w-auto"
        />
      </label>
      <label>
        <span className="label text-xs">Đến ngày</span>
        <input
          type="date"
          value={to}
          onChange={(e) => setTo(e.target.value)}
          className="input h-9 w-auto"
        />
      </label>
      <button type="submit" className="btn btn-primary">
        Áp dụng
      </button>
    </form>
  );
}
