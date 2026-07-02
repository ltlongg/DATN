import { apiFetch } from "@/api/client";
import type { UserCreateInput, UserOut, UserUpdateInput } from "@/types/admin";

export function listUsers(): Promise<UserOut[]> {
  return apiFetch<UserOut[]>("/api/admin/users");
}

export function createUser(input: UserCreateInput): Promise<UserOut> {
  return apiFetch<UserOut>("/api/admin/users", { method: "POST", body: input });
}

export function updateUser(id: string, patch: UserUpdateInput): Promise<UserOut> {
  return apiFetch<UserOut>(`/api/admin/users/${id}`, { method: "PATCH", body: patch });
}
