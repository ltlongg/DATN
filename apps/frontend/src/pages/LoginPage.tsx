import { Link, Navigate } from "react-router-dom";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { GoogleButton } from "@/features/auth/GoogleButton";
import { LoginForm } from "@/features/auth/LoginForm";
import { useAuthStore } from "@/store/authStore";

export default function LoginPage() {
  const token = useAuthStore((s) => s.token);
  if (token) return <Navigate to="/" replace />;

  return (
    <AuthLayout title="Đăng nhập" subtitle="Chào mừng trở lại. Đăng nhập để tiếp tục hỏi đáp.">
      <LoginForm />
      <GoogleButton />
      <p className="mt-8 text-center text-sm text-ink-soft">
        Chưa có tài khoản?{" "}
        <Link to="/register" className="font-semibold text-brand hover:underline">
          Đăng ký
        </Link>
      </p>
    </AuthLayout>
  );
}
