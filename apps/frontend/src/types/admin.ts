/** Types Module 4 (admin nâng cao). Mirror apps/backend/app/schemas/{logs,user,cost}.py. */
import type { Citation, ProgressStep, Role, VisualizationPayload } from "@/types";

// --- Hội thoại & chất lượng ---
export interface ConversationLogItem {
  id: string;
  title: string;
  user_email: string;
  user_name: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ConversationLogResponse {
  items: ConversationLogItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface MessageQuality {
  retrieval_attempted: boolean;
  no_citation: boolean;
  low_confidence: boolean;
  clarification: boolean;
  has_warning: boolean;
}

export interface MessageLogItem {
  id: string;
  role: string;
  content: string;
  clarification_needed: boolean;
  citations: Citation[];
  visualization: VisualizationPayload | null;
  retrieval_mode: string;
  confidence: string | null;
  warnings: string[];
  /** Panel tiến trình đã lưu, KÈM `internals` từng bước. Rỗng với message user và với
   *  message lưu trước khi có B3. */
  steps: ProgressStep[];
  ttft_ms: number | null;
  created_at: string;
  quality: MessageQuality;
}

export interface ConversationLogDetail {
  id: string;
  title: string;
  user_email: string;
  user_name: string;
  created_at: string;
  updated_at: string;
  messages: MessageLogItem[];
}

export interface QualitySummary {
  total_assistant_messages: number;
  retrieval_attempted_count: number;
  no_citation_count: number;
  low_confidence_count: number;
  clarification_count: number;
  warning_count: number;
  /** TTFT: mẫu số riêng — message không đo được (ttft_ms null) không tính vào trung bình. */
  ttft_measured_count: number;
  avg_ttft_ms: number | null;
  p95_ttft_ms: number | null;
}

// --- Token theo hội thoại/message (song song chất lượng) ---
export interface TokenOverall {
  total_calls: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  avg_tokens_per_call: number;
}

export interface ConversationTokens {
  conversation_id: string;
  call_count: number;
  total_tokens: number;
}

export interface TokenSummary {
  overall: TokenOverall;
  by_conversation: ConversationTokens[];
}

export interface MessageTokenTaskRow {
  task: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface MessageTokens {
  message_id: string;
  total_tokens: number;
  rows: MessageTokenTaskRow[];
}

// --- Người dùng & quota ---
export interface UserOut {
  id: string;
  email: string;
  name: string;
  role: Role;
  is_active: boolean;
  question_quota: number | null;
  created_at: string;
}

export interface UserCreateInput {
  email: string;
  name: string;
  role: Role;
  password: string;
}

export interface UserUpdateInput {
  role?: Role;
  is_active?: boolean;
  question_quota?: number | null;
}

// --- Chi phí ---
export interface CostOverview {
  total_calls: number;
  total_tokens: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  avg_tokens_per_call: number;
}

export interface DailyCost {
  day: string;
  calls: number;
  total_tokens: number;
}

export interface TaskCost {
  task: string;
  calls: number;
  total_tokens: number;
}

export interface TopUserCost {
  user_id: string;
  email: string;
  name: string;
  total_tokens: number;
  call_count: number;
}

// --- Hoạt động hệ thống (activity log) — mirror apps/backend/app/schemas/activity.py ---
export interface ActivityLogItem {
  id: string;
  created_at: string;
  request_id: string | null;
  user_id: string | null;
  method: string;
  path: string;
  status_code: number;
  severity: "ok" | "error";
  latency_ms: number | null;
  error: string | null;
}

export interface ActivityLogResponse {
  items: ActivityLogItem[];
  total: number;
  limit: number;
  offset: number;
}

// --- Cấu hình hệ thống — mirror apps/backend/app/schemas/config.py (12 field áp dụng LIVE) ---
export interface SystemConfig {
  rag_top_k: number;
  graph_top_k: number;
  hybrid_candidate_k: number;
  hybrid_rrf_k: number;
  rerank_top_k: number;
  bm25_top_k: number;
  graph_max_seed_entities: number;
  graph_max_chunks_per_seed: number;
  graph_hub_source_count_threshold: number;
  graph_max_context_items: number;
  graph_max_path_hops: number;
  graph_path_hit_weight: number;
  updated_at: string;
}

export type SystemConfigUpdate = Partial<Omit<SystemConfig, "updated_at">>;
