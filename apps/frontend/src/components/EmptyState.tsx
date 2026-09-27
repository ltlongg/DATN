import type { ReactNode } from "react";
import { Inbox } from "lucide-react";

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-paper-border px-6 py-10 text-center text-sm text-ink-soft">
      <Inbox size={22} className="text-ink-faint" aria-hidden />
      {children}
    </div>
  );
}
