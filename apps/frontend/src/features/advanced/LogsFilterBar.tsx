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
    <form onSubmit={submit} className="card flex flex-wrap items-end gap-3 p-4">
      <label>
        <span className="label text-xs">Mã người dùng</span>
        <input
          value={anonId}
          onChange={(e) => setAnonId(e.target.value)}
          placeholder="user-1a2b3c4d"
          className="input h-9 w-auto"
        />
      </label>
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
      <label className="flex h-9 items-center gap-2 text-sm text-ink">
        <input
          type="checkbox"
          className="h-4 w-4 accent-brand"
          checked={flaggedOnly}
          onChange={(e) => setFlaggedOnly(e.target.checked)}
        />
        Chỉ hội thoại bị gắn cờ
      </label>
      <button type="submit" className="btn btn-primary">
        Lọc
      </button>
    </form>
  );
}
