import { apiFetch } from "@/api/client";
import type { ActivityLogResponse } from "@/types/admin";

export interface ActivityQuery {
  severity?: "ok" | "error";
  path?: string;
  limit?: number;
  offset?: number;
}

export function getActivity(params: ActivityQuery): Promise<ActivityLogResponse> {
  return apiFetch<ActivityLogResponse>("/api/admin/activity", { query: { ...params } });
}
