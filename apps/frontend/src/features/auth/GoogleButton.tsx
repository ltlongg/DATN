import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";
import { ApiError } from "@/api/client";
import { loginWithGoogle } from "@/api/auth";
import { redirectTargetFrom } from "@/features/auth/redirectTarget";
import { useAuthStore } from "@/store/authStore";

/**
 * Nút "Đăng nhập với Google" — dùng ở CẢ /login và /register (cùng một endpoint: người
 * dùng lần đầu thì backend tự tạo tài khoản).
 *
 * `GoogleOAuthProvider` bọc TẠI ĐÂY chứ không bọc toàn app: provider nạp script Google
 * Identity Services khi mount, khu chat/admin không cần tới.
 *
 * Chưa cấu hình VITE_GOOGLE_CLIENT_ID -> KHÔNG render gì (đừng để nút chết trên màn hình).
 */
export function GoogleButton() {
  const navigate = useNavigate();
  const location = useLocation();
  const setAuth = useAuthStore((s) => s.setAuth);
  const [error, setError] = useState<string | null>(null);
  const clientId = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";

  if (!clientId) return null;

  async function submitGoogle(credential: string) {
    setError(null);
    try {
      const res = await loginWithGoogle(credential);
      setAuth(res.access_token, res.user);
      navigate(redirectTargetFrom(location.state), { replace: true });
    } catch (e) {
      // account_link_required (409), account_locked (403), invalid_google_token (401),
      // google_unavailable (503) đều có message tiếng Việt sẵn từ backend.
      setError(e instanceof ApiError ? e.message : "Không đăng nhập được bằng Google.");
    }
  }

  return (
    <div className="mt-5">
      <div className="mb-5 flex items-center gap-3 text-xs font-semibold uppercase tracking-wide text-ink">
        <span className="h-px flex-1 bg-ink/25" />
        hoặc
        <span className="h-px flex-1 bg-ink/25" />
      </div>

      {/* `locale` là prop của PROVIDER (nó nạp script GIS kèm hl=vi), KHÔNG phải của
          <GoogleLogin> — đặt nhầm chỗ là TypeScript báo lỗi ngay. */}
      <GoogleOAuthProvider clientId={clientId} locale="vi">
        <div className="flex justify-center">
          <GoogleLogin
            // `credential` là ID token. Kiểu của nó là optional; thiếu thì báo lỗi chứ
            // KHÔNG im lặng bỏ qua (người dùng bấm mà không có gì xảy ra là tệ nhất).
            onSuccess={(res) =>
              res.credential
                ? void submitGoogle(res.credential)
                : setError("Không đăng nhập được bằng Google.")
            }
            onError={() => setError("Không đăng nhập được bằng Google.")}
            shape="pill"
            // width theo hợp đồng GIS là CHUỖI số pixel (tối đa "400") — không phải số,
            // không phải "100%". Muốn co giãn thì canh bằng div bọc ngoài.
            width="320"
          />
        </div>
      </GoogleOAuthProvider>

      {error && (
        <p role="alert" className="mt-3 text-center text-sm text-brand">
          {error}
        </p>
      )}
    </div>
  );
}
