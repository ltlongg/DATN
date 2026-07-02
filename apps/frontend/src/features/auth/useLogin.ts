import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import { login } from "@/api/auth";
import { useAuthStore } from "@/store/authStore";

/** Đăng nhập -> lưu auth -> về khu user. Lỗi hiển thị message tiếng Việt từ backend. */
export function useLogin() {
  const navigate = useNavigate();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(email: string, password: string) {
    setPending(true);
    setError(null);
    try {
      const res = await login(email, password);
      setAuth(res.access_token, res.user);
      navigate("/", { replace: true });
    } catch (e) {
      // Backend trả message tiếng Việt sẵn (invalid_credentials, account_locked).
      setError(e instanceof ApiError ? e.message : "Không đăng nhập được. Thử lại sau.");
    } finally {
      setPending(false);
    }
  }

  return { submit, pending, error };
}
