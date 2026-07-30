import { useState, type FormEvent } from "react";

export interface LogsFilterValue {
  user_email: string;
  from_date: string;
  to_date: string;
}

/** Lọc hội thoại theo email + khoảng ngày. */
export function LogsFilterBar({ onApply }: { onApply: (v: LogsFilterValue) => void }) {
  const [email, setEmail] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    onApply({ user_email: email.trim(), from_date: from, to_date: to });
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <label className="text-sm">
        <span className="block text-xs text-ink-soft">Email người dùng</span>
        <input
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="user@example.com"
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
      <button
        type="submit"
        className="rounded-md bg-brand px-3 py-1.5 text-sm text-brand-fg hover:bg-brand-dark"
      >
        Lọc
      </button>
    </form>
  );
}
