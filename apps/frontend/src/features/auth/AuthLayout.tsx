import type { ReactNode } from "react";
import background from "@/assets/background.png";
import { BrandMark } from "@/components/BrandMark";

interface AuthLayoutProps {
  title: string;
  subtitle: string;
  children: ReactNode;
}

/**
 * Bố cục dùng chung cho /login và /register: màn rộng chia đôi — trái là ảnh minh hoạ +
 * thông điệp sản phẩm, phải là form trên nền trắng. Màn hẹp chỉ còn cột form.
 */
export function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  return (
    <main className="flex h-full bg-paper-card">
      <aside className="relative hidden flex-1 overflow-hidden lg:block">
        <img
          src={background}
          alt=""
          className="absolute inset-0 h-full w-full object-cover object-[65%_center]"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-night/90 via-night/30 to-transparent" />
      </aside>

      {/* Chỉ cột form cuộn (chừa sẵn rãnh scrollbar) và neo form theo mép trên — để chuyển
          giữa /login (ngắn) và /register (dài) không làm cột ảnh co lại hay tiêu đề nhảy. */}
      <section className="flex w-full justify-center overflow-y-auto px-6 pb-12 pt-12 [scrollbar-gutter:stable] lg:w-[480px] lg:shrink-0 lg:pt-[12vh] xl:w-[560px]">
        <div className="w-full max-w-sm">
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <BrandMark />
            <span className="font-serif text-lg font-bold text-ink">Sử Việt</span>
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-ink">{title}</h1>
          <p className="mt-2 text-sm text-ink-soft">{subtitle}</p>
          <div className="mt-8">{children}</div>
        </div>
      </section>
    </main>
  );
}
