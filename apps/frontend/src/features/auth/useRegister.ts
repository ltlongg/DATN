import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "@/api/client";
import { register } from "@/api/auth";
import { redirectTargetFrom } from "@/features/auth/redirectTarget";
import { useAuthStore } from "@/store/authStore";

/** Đăng ký -> backend cấp token luôn -> lưu auth -> vào thẳng khu hỏi đáp. */
export function useRegister() {
  const navigate = useNavigate();
  const location = useLocation();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(email: string, name: string, password: string) {
    setPending(true);
    setError(null);
    try {
      const res = await register(email, name, password);
      setAuth(res.access_token, res.user);
      navigate(redirectTargetFrom(location.state), { replace: true });
    } catch (e) {
      // email_taken (409) và validation_error (422) đều có message tiếng Việt từ backend.
      setError(e instanceof ApiError ? e.message : "Không đăng ký được. Thử lại sau.");
    } finally {
      setPending(false);
    }
  }

  return { submit, pending, error };
}
