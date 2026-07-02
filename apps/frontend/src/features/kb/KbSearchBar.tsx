import { useState, type FormEvent, type ReactNode } from "react";

/** Ô tìm kiếm (submit -> onSearch) + slot filter phụ (select confidence/type…). */
export function KbSearchBar({
  placeholder,
  onSearch,
  children,
}: {
  placeholder: string;
  onSearch: (q: string) => void;
  children?: ReactNode;
}) {
  const [q, setQ] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    onSearch(q.trim());
  }

  return (
    <form onSubmit={submit} className="flex flex-wrap items-center gap-2">
      <input
        value={q}
        onChange={(e) => setQ(e.target.value)}
        placeholder={placeholder}
        className="flex-1 rounded-md border border-paper-border px-3 py-1.5 text-sm outline-none focus:border-brand"
      />
      {children}
      <button
        type="submit"
        className="rounded-md bg-brand px-3 py-1.5 text-sm text-brand-fg hover:bg-brand-dark"
      >
        Tìm
      </button>
    </form>
  );
}
