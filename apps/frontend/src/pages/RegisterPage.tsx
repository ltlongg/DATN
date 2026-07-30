import { Link, Navigate } from "react-router-dom";
import { AuthLayout } from "@/features/auth/AuthLayout";
import { GoogleButton } from "@/features/auth/GoogleButton";
import { RegisterForm } from "@/features/auth/RegisterForm";
import { useAuthStore } from "@/store/authStore";

export default function RegisterPage() {
  const token = useAuthStore((s) => s.token);
  if (token) return <Navigate to="/" replace />;

  return (
    <AuthLayout title="Đăng ký">
      <RegisterForm />
      <GoogleButton />
      <p className="mt-4 text-center text-sm text-ink">
        Đã có tài khoản?{" "}
        <Link to="/login" className="font-semibold text-brand hover:underline">
          Đăng nhập
        </Link>
      </p>
    </AuthLayout>
  );
}
