import type { ReactNode } from "react";

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-paper-border p-8 text-center text-sm text-ink-soft">
      {children}
    </div>
  );
}
