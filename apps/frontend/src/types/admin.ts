/** Types Module 4 (admin nâng cao). Mirror apps/backend/app/schemas/{logs,user,cost}.py. */
import type { Citation, Role, VisualizationPayload } from "@/types";

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
