import { apiFetch } from "@/api/client";
import type { LoginResponse, User } from "@/types";

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiFetch<LoginResponse>("/api/auth/login", {
    method: "POST",
    body: { email, password },
  });
}

export function getMe(): Promise<User> {
  return apiFetch<User>("/api/auth/me");
}

export function logout(): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>("/api/auth/logout", { method: "POST" });
}
