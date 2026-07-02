import { Navigate } from "react-router-dom";
import { LoginForm } from "@/features/auth/LoginForm";
import { useAuthStore } from "@/store/authStore";

const APP_NAME = import.meta.env.VITE_APP_NAME ?? "Agentic RAG — Lịch sử Việt Nam";

export default function LoginPage() {
  const token = useAuthStore((s) => s.token);
  if (token) return <Navigate to="/" replace />;

  return (
    <main className="flex min-h-full items-center justify-center p-6">
      <div className="w-full max-w-sm rounded-xl border border-paper-border bg-paper-card p-8 shadow-sm">
        <h1 className="text-center text-2xl font-bold text-brand">{APP_NAME}</h1>
        <p className="mt-1 mb-6 text-center text-sm text-ink-soft">
          Hỏi đáp lịch sử Việt Nam có căn cứ từ tài liệu.
        </p>
        <LoginForm />
      </div>
    </main>
  );
}
