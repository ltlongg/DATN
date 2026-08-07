import { Link, Navigate } from "react-router-dom";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { GoogleButton } from "@/features/auth/GoogleButton";
import { LoginForm } from "@/features/auth/LoginForm";
import { useAuthStore } from "@/store/authStore";

export default function LoginPage() {
  const token = useAuthStore((s) => s.token);
  if (token) return <Navigate to="/" replace />;

  return (
    <AuthLayout title="Đăng nhập">
      <LoginForm />
      <GoogleButton />
      <p className="mt-5 text-center text-sm text-ink">
        Chưa có tài khoản?{" "}
        <Link to="/register" className="font-bold text-ink transition hover:underline">
          Đăng ký
        </Link>
      </p>
    </AuthLayout>
  );
}
