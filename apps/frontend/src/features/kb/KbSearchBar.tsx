import { useState, type FormEvent, type ReactNode } from "react";
import { Search } from "lucide-react";

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
      <div className="relative min-w-[12rem] flex-1">
        <Search
          size={16}
          className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint"
          aria-hidden
        />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder={placeholder}
          aria-label={placeholder}
          className="input h-9 pl-9"
        />
      </div>
      {children}
      <button type="submit" className="btn btn-primary">
        Tìm
      </button>
    </form>
  );
}
