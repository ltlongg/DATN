import { apiFetch } from "@/api/client";
import type { LoginResponse, User } from "@/types";

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: { email, password },
  });
}

/** Đăng ký công khai — backend trả luôn token (auto-login), role hardcode "user". */
export function register(
  email: string,
  name: string,
  password: string,
): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/auth/register", {
    method: "POST",
    body: { email, name, password },
  });
}

/**
 * Đăng nhập Google. `credential` = ID token do nút Sign in with Google trả về; backend
 * verify chữ ký rồi cấp JWT của hệ thống mình. Cùng một endpoint cho "đăng nhập" lẫn
 * "đăng ký bằng Google" — lần đầu backend tự tạo tài khoản.
 */
export function loginWithGoogle(credential: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/auth/google", {
    method: "POST",
    body: { credential },
  });
}

export function getMe(): Promise<User> {
  return apiFetch<User>("/api/auth/me");
}

export function logout(): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/api/auth/logout", { method: "POST" });
}
