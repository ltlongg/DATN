import { buildUrl } from "@/api/client";
import { useAuthStore } from "@/store/authStore";
import type { Citation, DebugInfo, VisualizationPayload } from "@/types";

/**
 * SSE client cho POST /api/chat/conversations/{id}/ask.
 * Dùng fetch + ReadableStream tay (EventSource không set được Bearer header).
 * Backend luôn streaming; lỗi TRƯỚC khi mở stream -> HTTP 4xx/5xx {code,message};
 * lỗi SAU khi mở -> event `error`. Cả hai đều đi qua onError.
 */

export interface StatusEvent {
  node: string;
  msg: string;
}

export interface DonePayload {
  confidence: string | null;
  retrieval_mode: string;
  warnings: string[];
  conversation_id: string;
  message_id: string | null;
}

export interface AskHandlers {
  onStatus?: (d: StatusEvent) => void;
  onToken?: (text: string) => void;
  onCitations?: (citations: Citation[]) => void;
  onVisualization?: (visualization: VisualizationPayload | null) => void;
  onClarification?: (question: string) => void;
  onRegenerating?: () => void;
  onBlocked?: () => void;
  onError?: (err: { code: string; message: string }) => void;
  onDebug?: (debug: DebugInfo) => void;
  onDone?: (done: DonePayload) => void;
}

export interface AskStreamController {
  abort: () => void;
  /** Resolve khi stream xử lý xong (kể cả lỗi/abort). Hữu ích cho test + caller chờ. */
  done: Promise<void>;
}

/** 3 mode truy hồi user chọn tay; mặc định hybrid (hành vi cũ). */
export type RetrievalMode = "hybrid" | "traditional" | "graph";

export interface AskBody {
  question: string;
  mode: RetrievalMode;
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
    case "status":
      h.onStatus?.({ node: String(d.node ?? ""), msg: String(d.msg ?? "") });
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
    case "debug":
      h.onDebug?.((d.debug as DebugInfo) ?? {});
      break;
    case "done":
      h.onDone?.({
        confidence: (d.confidence as string | null) ?? null,
        retrieval_mode: String(d.retrieval_mode ?? "none"),
        warnings: (d.warnings as string[]) ?? [],
        conversation_id: String(d.conversation_id ?? ""),
        message_id: (d.message_id as string | null) ?? null,
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
