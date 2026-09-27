import type { ReactNode } from "react";

/** Nhãn + ô nhập cho form khu admin (control con tự mang class `.input`). */
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
    </label>
  );
}
