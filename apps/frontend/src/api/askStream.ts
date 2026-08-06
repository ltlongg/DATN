import { buildUrl } from "@/api/client";
import { useAuthStore } from "@/store/authStore";
import type {
  Citation,
  ProgressStep,
  StepInternalRow,
  StepState,
  VisualizationPayload,
} from "@/types";

/**
 * SSE client cho POST /api/chat/conversations/{id}/ask.
 * Dùng fetch + ReadableStream tay (EventSource không set được Bearer header).
 * Backend luôn streaming; lỗi TRƯỚC khi mở stream -> HTTP 4xx/5xx {code,message};
 * lỗi SAU khi mở -> event `error`. Cả hai đều đi qua onError.
 */

/** Khai báo danh sách dòng của panel tiến trình — chưa có state (đi riêng qua `step`). */
export type StepDeclaration = Pick<ProgressStep, "id" | "label" | "kind">;

/**
 * Cập nhật MỘT dòng đã khai báo. `detail`/`internals` vắng mặt = giữ nguyên cái cũ.
 *
 * `internals` chỉ tới với admin bật debug — backend bóc khỏi event `step` cho mọi lượt còn
 * lại (`api/chat.py::_visible_step`), nên ở đây "vắng mặt" là chuyện bình thường.
 */
export interface StepUpdate {
  id: string;
  state: StepState;
  detail?: string;
  internals?: StepInternalRow[];
}

export interface DonePayload {
  confidence: string | null;
  retrieval_mode: string;
  warnings: string[];
  conversation_id: string;
  message_id: string | null;
  /** TTFT (ms) backend đo: nhận /ask -> token đầu tiên. null nếu chưa có token nào. */
  ttft_ms: number | null;
}

export interface AskHandlers {
  onSteps?: (steps: StepDeclaration[]) => void;
  onStep?: (step: StepUpdate) => void;
  onToken?: (text: string) => void;
  onCitations?: (citations: Citation[]) => void;
  onVisualization?: (visualization: VisualizationPayload | null) => void;
  onClarification?: (question: string) => void;
  onRegenerating?: () => void;
  onBlocked?: () => void;
  onError?: (err: { code: string; message: string }) => void;
  onDone?: (done: DonePayload) => void;
}

export interface AskStreamController {
  abort: () => void;
  /** Resolve khi stream xử lý xong (kể cả lỗi/abort). Hữu ích cho test + caller chờ. */
  done: Promise<void>;
}

/**
 * Body gửi lên `/ask`. KHÔNG có `mode`: agent tự chọn cách truy hồi (bậc B2). Backend mặc
 * định "auto" khi thiếu field. Override traditional/hybrid vẫn gọi được ở tầng API
 * (curl/Swagger) để so sánh lúc đánh giá — chỉ frontend không gửi.
 * Xem docs/plan/agentic-retrieval-loop-plan.md §0.1.
 */
export interface AskBody {
  question: string;
  /**
   * Bật tầng 2 của panel tiến trình (`internals` trong event `step`). Backend ép về false
   * cho user thường, nên đây là ĐỀ NGHỊ chứ không phải quyền — nhưng vẫn phải gửi, vì
   * backend dùng chính cờ này để quyết định có forward internals hay không.
   */
  debug: boolean;
}

export function openAskStream(
  conversationId: string,
  body: AskBody,
  handlers: AskHandlers,
): AskStreamController {
  const controller = new AbortController();
  const done = run(conversationId, body, handlers, controller.signal);
  return { abort: () => controller.abort(), done };
}

async function run(
  conversationId: string,
  body: AskBody,
  handlers: AskHandlers,
  signal: AbortSignal,
): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  const token = useAuthStore.getState().token;
  if (token) headers.Authorization = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(buildUrl(`/api/chat/conversations/${conversationId}/ask`), {
      method: "POST",
      headers,
      body: JSON.stringify(body),
      signal,
    });
  } catch {
    if (!signal.aborted) {
      handlers.onError?.({ code: "network_error", message: "Không kết nối được máy chủ." });
    }
    return;
  }

  // Lỗi TRƯỚC khi mở stream: backend trả HTTP status + body {code,message}.
  if (res.status === 401) {
    useAuthStore.getState().clear();
    handlers.onError?.({ code: "unauthorized", message: "Phiên đăng nhập đã hết hạn." });
    return;
  }
  if (!res.ok || !res.body) {
    handlers.onError?.(await parseErrorBody(res));
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      buffer = drainEvents(buffer, handlers);
    }
    buffer += decoder.decode();
    // Event cuối có thể thiếu "\n\n" (phòng thủ) -> ép parse nốt.
    if (buffer.trim() !== "") dispatch(parseBlock(buffer), handlers);
  } catch {
    if (!signal.aborted) {
      handlers.onError?.({ code: "stream_error", message: "Lỗi khi đọc luồng trả lời." });
    }
  }
}

/** Cắt các event hoàn chỉnh (ngăn bởi "\n\n"), dispatch, trả phần dư chưa đủ. */
function drainEvents(buffer: string, handlers: AskHandlers): string {
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  for (const block of parts) {
    dispatch(parseBlock(block), handlers);
  }
  return rest;
}

interface SseEvent {
  event: string;
  data: unknown;
}

function parseBlock(block: string): SseEvent | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    else if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null; // block hỏng -> bỏ qua, không vỡ stream
  }
}

function dispatch(evt: SseEvent | null, h: AskHandlers): void {
  if (!evt) return;
  const d = evt.data as Record<string, unknown>;
  switch (evt.event) {
    case "steps":
      h.onSteps?.((d.steps as StepDeclaration[]) ?? []);
      break;
    case "step":
      h.onStep?.({
        id: String(d.id ?? ""),
        state: (d.state as StepState) ?? "pending",
        // Phân biệt "không gửi detail" với "gửi detail rỗng": chỉ có mặt mới ghi đè. Cùng
        // luật cho `internals` — người dùng thường không nhận field này (backend bóc), và
        // "không gửi" phải khác "gửi mảng rỗng".
        ...("detail" in d ? { detail: String(d.detail ?? "") } : {}),
        ...("internals" in d
          ? { internals: (d.internals as StepInternalRow[]) ?? [] }
          : {}),
      });
      break;
    case "token":
      h.onToken?.(String(d.text ?? ""));
      break;
    case "citations":
      h.onCitations?.((d.citations as Citation[]) ?? []);
      break;
    case "visualization":
      h.onVisualization?.((d.visualization as VisualizationPayload | null) ?? null);
      break;
    case "clarification":
      h.onClarification?.(String(d.question ?? ""));
      break;
    case "regenerating":
      h.onRegenerating?.();
      break;
    case "blocked":
      h.onBlocked?.();
      break;
    case "error":
      h.onError?.({ code: String(d.code ?? "error"), message: String(d.message ?? "") });
      break;
    case "done":
      h.onDone?.({
        confidence: (d.confidence as string | null) ?? null,
        retrieval_mode: String(d.retrieval_mode ?? "none"),
        warnings: (d.warnings as string[]) ?? [],
        conversation_id: String(d.conversation_id ?? ""),
        message_id: (d.message_id as string | null) ?? null,
        ttft_ms: typeof d.ttft_ms === "number" ? d.ttft_ms : null,
      });
      break;
    // event lạ -> bỏ qua (không vỡ)
  }
}

async function parseErrorBody(res: Response): Promise<{ code: string; message: string }> {
  try {
    const data = (await res.json()) as { code?: string; message?: string };
    return { code: data.code ?? "error", message: data.message ?? "Có lỗi xảy ra." };
  } catch {
    return { code: "error", message: `Lỗi ${res.status}.` };
  }
}
