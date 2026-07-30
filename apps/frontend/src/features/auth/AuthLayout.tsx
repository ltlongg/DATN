import type { ReactNode } from "react";
import background from "@/assets/background.png";

const APP_NAME = import.meta.env.VITE_APP_NAME ?? "Agentic RAG — Lịch sử Việt Nam";

interface AuthLayoutProps {
  title: string;
  children: ReactNode;
}

/**
 * Bố cục dùng chung cho /login và /register: ảnh nền phủ kín, card form nổi ở giữa.
 * Tách ra để lần sửa ảnh nền / thương hiệu chỉ phải sửa một chỗ.
 */
export function AuthLayout({ title, children }: AuthLayoutProps) {
  return (
    <main className="relative flex min-h-full items-center justify-center p-6">
      {/* Ảnh nền phủ kín + lớp phủ tối nhẹ cho form dễ đọc */}
      <img src={background} alt="" className="absolute inset-0 h-full w-full object-cover" />
      <div className="absolute inset-0 bg-ink/40" />

      {/* Card form nổi trên nền — hiệu ứng kính mờ (glassmorphism) */}
      <div className="relative w-full max-w-md rounded-2xl border border-white/40 bg-paper-card/10 p-8 shadow-2xl backdrop-blur-md">
        <header className="mb-6 flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand font-serif text-lg font-bold text-brand-fg">
            LS
          </span>
          <span className="font-serif text-base font-semibold leading-tight text-ink">
            {APP_NAME}
          </span>
        </header>

        <h2 className="font-serif text-2xl font-bold tracking-tight text-brand-dark">{title}</h2>
        <div className="mt-6">{children}</div>
      </div>
    </main>
  );
}
