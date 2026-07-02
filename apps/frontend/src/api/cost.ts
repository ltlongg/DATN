import { apiFetch } from "@/api/client";
import type { CostOverview, DailyCost, TaskCost, TopUserCost } from "@/types/admin";

export interface CostRange {
  from_date?: string;
  to_date?: string;
}

export function getCostOverview(range: CostRange): Promise<CostOverview> {
  return apiFetch<CostOverview>("/api/admin/cost/overview", { query: { ...range } });
}

export function getCostByDay(range: CostRange): Promise<DailyCost[]> {
  return apiFetch<DailyCost[]>("/api/admin/cost/by-day", { query: { ...range } });
}

export function getCostByTask(range: CostRange): Promise<TaskCost[]> {
  return apiFetch<TaskCost[]>("/api/admin/cost/by-task", { query: { ...range } });
}

export function getTopUsers(range: CostRange & { limit?: number }): Promise<TopUserCost[]> {
  return apiFetch<TopUserCost[]>("/api/admin/cost/top-users", { query: { ...range } });
}
