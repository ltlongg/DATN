import { Navigate } from "react-router-dom";
import { LoginForm } from "@/features/auth/LoginForm";
import { useAuthStore } from "@/store/authStore";
import loginHero from "@/assets/login-hero.jpg";

const APP_NAME = import.meta.env.VITE_APP_NAME ?? "Agentic RAG — Lịch sử Việt Nam";

export default function LoginPage() {
  const token = useAuthStore((s) => s.token);
  if (token) return <Navigate to="/" replace />;

  return (
    <main className="grid min-h-full md:grid-cols-5">
      {/* Cột ảnh bìa — chiếm 3/5, phủ kín. Ẩn trên màn nhỏ. */}
      <section className="relative hidden md:col-span-3 md:block">
        <img src={loginHero} alt="" className="absolute inset-0 h-full w-full object-cover" />
      </section>

      {/* Cột đăng nhập — chiếm 2/5 */}
      <section className="flex flex-col justify-between p-8 md:col-span-2">
        {/* Thương hiệu ở đầu cột */}
        <header className="flex items-center gap-3">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand font-serif text-lg font-bold text-brand-fg">
            LS
          </span>
          <span className="font-serif text-base font-semibold leading-tight text-ink">
            {APP_NAME}
          </span>
        </header>

        {/* Khối đăng nhập ở giữa */}
        <div className="mx-auto w-full max-w-sm py-8">
          {/* Ảnh banner cho màn hình nhỏ (khi cột ảnh bị ẩn) */}
          <img
            src={loginHero}
            alt=""
            className="mb-6 h-36 w-full rounded-xl object-cover md:hidden"
          />
          <h2 className="font-serif text-2xl font-bold text-brand">Đăng nhập</h2>
          <p className="mt-1 mb-6 text-sm text-ink-soft">
            Đăng nhập để bắt đầu hỏi đáp lịch sử Việt Nam có căn cứ từ tài liệu.
          </p>
          <LoginForm />

          <ul className="mt-8 space-y-2 text-sm text-ink-soft">
            <li className="flex items-start gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-muted" />
              Câu trả lời trích dẫn nguồn từ tài liệu gốc.
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-muted" />
              Sự kiện hiển thị trên bản đồ và timeline.
            </li>
            <li className="flex items-start gap-2">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-muted" />
              Kết hợp RAG, GraphRAG và hybrid retrieval.
            </li>
          </ul>
        </div>

        {/* Footer cột */}
        <footer className="text-center text-xs text-ink-soft/70">
          Đồ án tốt nghiệp · Agentic RAG cho lịch sử Việt Nam
        </footer>
      </section>
    </main>
  );
}
