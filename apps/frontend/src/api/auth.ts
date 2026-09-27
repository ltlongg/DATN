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

export function updatePreferences(prefs: { share_conversations: boolean }): Promise<User> {
  return apiFetch<User>("/api/auth/me/preferences", { method: "PATCH", body: prefs });
}

/** Chỉ sửa được họ tên — email là định danh đăng nhập, không cho tự đổi. */
export function updateProfile(profile: { name: string }): Promise<User> {
  return apiFetch<User>("/api/auth/me/profile", { method: "PATCH", body: profile });
}

/** Sai mật khẩu hiện tại -> 400 `invalid_current_password` (không phải 401, nên không bị
 * client coi là hết phiên). */
export function changePassword(body: {
  current_password: string;
  new_password: string;
}): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/api/auth/me/password", { method: "POST", body });
}

export function logout(): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/api/auth/logout", { method: "POST" });
}
