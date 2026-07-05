import { apiFetch } from "@/api/client";
import type {
  ConversationLogDetail,
  ConversationLogResponse,
  MessageTokens,
  QualitySummary,
  TokenSummary,
} from "@/types/admin";

export interface LogsFilter {
  user_email?: string;
  from_date?: string;
  to_date?: string;
  limit?: number;
  offset?: number;
}

export function listConversationLogs(f: LogsFilter): Promise<ConversationLogResponse> {
  return apiFetch<ConversationLogResponse>("/api/admin/logs/conversations", { query: { ...f } });
}

export function getConversationLog(id: string): Promise<ConversationLogDetail> {
  return apiFetch<ConversationLogDetail>(`/api/admin/logs/conversations/${id}`);
}

export function getQualitySummary(range: {
  from_date?: string;
  to_date?: string;
}): Promise<QualitySummary> {
  return apiFetch<QualitySummary>("/api/admin/logs/quality-summary", { query: { ...range } });
}

export function getTokenSummary(range: {
  from_date?: string;
  to_date?: string;
}): Promise<TokenSummary> {
  return apiFetch<TokenSummary>("/api/admin/logs/token-summary", { query: { ...range } });
}

export function getConversationTokens(id: string): Promise<MessageTokens[]> {
  return apiFetch<MessageTokens[]>(`/api/admin/logs/conversations/${id}/tokens`);
}
