import type { ReactNode } from "react";
import background from "@/assets/background.png";

interface AuthLayoutProps {
  title: string;
  children: ReactNode;
}

/**
 * Bố cục dùng chung cho /login và /register: ảnh nền phủ kín, card form nổi ở giữa.
 * Tách ra để lần sửa ảnh nền chỉ phải sửa một chỗ.
 */
export function AuthLayout({ title, children }: AuthLayoutProps) {
  return (
    <main className="relative flex min-h-full items-center justify-center p-6">
      {/* Ảnh nền phủ kín + lớp phủ tối nhẹ cho form dễ đọc */}
      <img src={background} alt="" className="absolute inset-0 h-full w-full object-cover" />
      <div className="absolute inset-0 bg-ink/40" />

      {/* Card form nổi trên nền — hiệu ứng kính mờ (glassmorphism) */}
      <div className="relative w-full max-w-md rounded-3xl border border-white/40 bg-paper-card/10 p-8 shadow-2xl backdrop-blur-md">
        <h2 className="text-center font-serif text-2xl font-semibold text-ink">{title}</h2>
        <div className="mt-6">{children}</div>
      </div>
    </main>
  );
}
