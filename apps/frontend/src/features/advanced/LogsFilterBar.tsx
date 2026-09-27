import { useState, type FormEvent } from "react";

export interface LogsFilterValue {
  user_anon_id: string;
  flagged_only: boolean;
  from_date: string;
  to_date: string;
}

/** Lọc hội thoại theo mã ẩn danh + chỉ hội thoại bị gắn cờ + khoảng ngày. Không lọc theo
 * email: admin không được tra hội thoại của một người cụ thể. */
export function LogsFilterBar({ onApply }: { onApply: (v: LogsFilterValue) => void }) {
  const [anonId, setAnonId] = useState("");
  const [flaggedOnly, setFlaggedOnly] = useState(false);
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    onApply({
      user_anon_id: anonId.trim(),
      flagged_only: flaggedOnly,
      from_date: from,
      to_date: to,
    });
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <label className="text-sm">
        <span className="block text-xs text-ink-soft">Mã người dùng</span>
        <input
          value={anonId}
          onChange={(e) => setAnonId(e.target.value)}
          placeholder="user-1a2b3c4d"
          className="rounded-md border border-paper-border px-2 py-1.5 outline-none focus:border-brand"
        />
      </label>
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
      <label className="flex items-center gap-2 py-1.5 text-sm text-ink">
        <input
          type="checkbox"
          checked={flaggedOnly}
          onChange={(e) => setFlaggedOnly(e.target.checked)}
        />
        Chỉ hội thoại bị gắn cờ
      </label>
      <button
        type="submit"
        className="rounded-md bg-brand px-3 py-1.5 text-sm text-brand-fg hover:bg-brand-dark"
      >
        Lọc
      </button>
    </form>
  );
}
