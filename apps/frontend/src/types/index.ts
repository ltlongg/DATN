/**
 * TS mirror của Pydantic schema backend/agent-service.
 * Nguồn: apps/backend/app/schemas/{auth,chat,document}.py,
 *        apps/agent-service/app/schemas/{ask,visualization}.py.
 * Chỉ khai báo type của Pha 1–5 (auth/chat/viz/document). Type Module 5 (KB) và Module 4
 * (logs/users/cost) khai báo ở phase tương ứng để giữ file tập trung.
 */

export type Role = "admin" | "user";

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

/** Toàn văn chunk cho modal xem nguồn (GET /api/chat/sources/{chunk_id}). Không có
 * `source_file`/`chunk_index`: UI không bao giờ hiện tên file. */
export interface SourceDetail {
  chunk_id: string;
  text: string;
  heading_path: string[];
  start_line: number | null;
  end_line: number | null;
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

/**
 * Một dòng của panel tiến trình (B3). `pending` là state DUY NHẤT agent không phát: nó
 * nghĩa là "đã khai báo trong danh sách nhưng chưa chạy tới" — và sau khi stream đóng thì
 * đọc là "bước này không chạy" (vd retrieve lỗi nên không tới lượt soạn bài).
 */
export type StepState = "pending" | "running" | "done" | "partial";

/** Một dòng của bảng tầng 2. `value` đã được agent format sẵn thành chuỗi. */
export interface StepInternalRow {
  label: string;
  value: string;
}

export interface ProgressStep {
  id: string;
  label: string;
  kind: "system" | "retrieve";
  state: StepState;
  /** Dòng phụ nói KẾT QUẢ, do agent ghép bằng code (không LLM). */
  detail?: string | null;
  /**
   * Tầng 2 — số liệu thô của ĐÚNG bước này (thay DebugPanel cũ, xoá 2026-08-01). Vắng mặt
   * với người dùng thường: backend bóc khỏi event `step` khi `debug=False`, nên đây không
   * phải chỗ gác quyền, chỉ là chỗ hiển thị thứ đã tới nơi.
   */
  internals?: StepInternalRow[] | null;
}

/** = MessageOut (backend). `citations`/`visualization`/`steps` đã lưu theo message. */
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
  /** Chuỗi bước đã chạy; rỗng với message user và message lưu trước khi có B3. */
  steps: ProgressStep[];
  /** TTFT (ms): từ lúc gửi câu hỏi tới token đầu tiên. null với message user. */
  ttft_ms: number | null;
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
  /** Khóa nối xuống kho tri thức (`rag_chunks.metadata.source_file`). null = chưa gắn nguồn. */
  source_file: string | null;
  /** Đếm THẬT từ kho, không phải số nhập tay. */
  chunk_count: number;
  event_count: number;
  created_at: string;
  updated_at: string;
}

/** Nguồn có thật trong kho tri thức. `document_id = null` = chưa khai báo ở danh mục. */
export interface KbSource {
  source_file: string;
  chunk_count: number;
  event_count: number;
  document_id: string | null;
}
