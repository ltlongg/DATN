import { apiFetch } from "@/api/client";
import type { SystemConfig, SystemConfigUpdate } from "@/types/admin";

export function getSystemConfig(): Promise<SystemConfig> {
  return apiFetch<SystemConfig>("/api/admin/config");
}

export function updateSystemConfig(patch: SystemConfigUpdate): Promise<SystemConfig> {
  return apiFetch<SystemConfig>("/api/admin/config", { method: "PUT", body: patch });
}
