/**
 * TS mirror của Pydantic schema backend/agent-service.
 * Nguồn: apps/backend/app/schemas/{auth,chat,document}.py,
 *        apps/agent-service/app/schemas/{ask,visualization}.py.
 * Chỉ khai báo type của Pha 1–5 (auth/chat/viz/document). Type Module 5 (KB) và Module 4
 * (logs/users/cost) khai báo ở phase tương ứng để giữ file tập trung.
 */

export type Role = "admin" | "teacher";

export type AnswerConfidence = "cao" | "vừa" | "thấp" | "không đủ dữ liệu";

export interface User {
  id: string;
  email: string;
  name: string;
  role: Role;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface Conversation {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface Citation {
  chunk_id: string;
  source_file?: string | null;
  chunk_index?: number | null;
  start_line?: number | null;
  end_line?: number | null;
  heading_path: string[];
  quote?: string | null;
}

export interface MapMarker {
  event_id: string;
  label: string;
  summary: string;
  location: string;
  lat: number;
  lon: number;
  confidence: string;
  time_start?: string | null;
}

export interface TimelineItem {
  event_id: string;
  label: string;
  summary: string;
  time_start: string;
  time_end?: string | null;
  confidence: string;
  locations: string[];
  located: boolean;
}

export interface VisualizationPayload {
  markers: MapMarker[];
  timeline: TimelineItem[];
  event_count: number;
  unplaced_count: number;
}

/** = MessageOut (backend). `citations`/`visualization` đã lưu theo message. */
export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  clarification_needed: boolean;
  citations: Citation[];
  visualization: VisualizationPayload | null;
  retrieval_mode: string;
  confidence: string | null;
  warnings: string[];
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export type DocumentStatus = "draft" | "indexing" | "indexed" | "failed";

export interface Document {
  id: string;
  name: string;
  type: string;
  status: DocumentStatus;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

// --- SSE debug payload (chỉ admin, gom 1 lần trước `done`) ---
export interface DebugInfo {
  build_query?: {
    standalone_query?: string;
    route?: string;
    mentioned_entities?: string[];
  };
  retrieve?: {
    chunks?: number;
    graph_context?: number;
  };
}
