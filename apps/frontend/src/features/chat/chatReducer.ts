import type { StatusEvent, DonePayload } from "@/api/askStream";
import type {
  Citation,
  DebugInfo,
  Message,
  VisualizationPayload,
} from "@/types";

/** Model hiển thị 1 dòng chat (user hoặc assistant). Assistant gom dần theo SSE. */
export interface ChatItem {
  id: string; // React key ổn định (assistantId lúc stream / message.id khi load lại)
  messageId: string | null; // id đã persist (từ event done); null khi chưa lưu
  role: "user" | "assistant";
  content: string;
  statusTrace: StatusEvent[];
  citations: Citation[];
  visualization: VisualizationPayload | null;
  clarificationNeeded: boolean;
  clarificationQuestion: string | null;
  confidence: string | null;
  retrievalMode: string | null;
  warnings: string[];
  debug: DebugInfo | null;
  error: { code: string; message: string } | null;
  blocked: boolean;
  streaming: boolean;
}

export type ChatAction =
  | { type: "load"; messages: Message[] }
  | { type: "startTurn"; userId: string; userText: string; assistantId: string }
  | { type: "status"; id: string; status: StatusEvent }
  | { type: "token"; id: string; text: string }
  | { type: "regenerating"; id: string }
  | { type: "citations"; id: string; citations: Citation[] }
  | { type: "visualization"; id: string; visualization: VisualizationPayload | null }
  | { type: "clarification"; id: string; question: string }
  | { type: "blocked"; id: string }
  | { type: "error"; id: string; error: { code: string; message: string } }
  | { type: "debug"; id: string; debug: DebugInfo }
  | { type: "done"; id: string; done: DonePayload };

function assistantBase(id: string): ChatItem {
  return {
    id,
    messageId: null,
    role: "assistant",
    content: "",
    statusTrace: [],
    citations: [],
    visualization: null,
    clarificationNeeded: false,
    clarificationQuestion: null,
    confidence: null,
    retrievalMode: null,
    warnings: [],
    debug: null,
    error: null,
    blocked: false,
    streaming: true,
  };
}

/** Message đã persist -> ChatItem (debug ephemeral nên không có khi load lại). */
export function messageToItem(m: Message): ChatItem {
  return {
    id: m.id,
    messageId: m.id,
    role: m.role,
    content: m.content,
    statusTrace: [],
    citations: m.citations,
    visualization: m.visualization,
    clarificationNeeded: m.clarification_needed,
    clarificationQuestion: m.clarification_needed ? m.content : null,
    confidence: m.confidence,
    retrievalMode: m.retrieval_mode,
    warnings: m.warnings,
    debug: null,
    error: null,
    blocked: false,
    streaming: false,
  };
}

function patch(state: ChatItem[], id: string, fn: (it: ChatItem) => ChatItem): ChatItem[] {
  return state.map((it) => (it.id === id ? fn(it) : it));
}

export function chatReducer(state: ChatItem[], action: ChatAction): ChatItem[] {
  switch (action.type) {
    case "load":
      return action.messages.map(messageToItem);

    case "startTurn":
      return [
        ...state,
        {
          ...assistantBase(action.userId),
          role: "user",
          content: action.userText,
          streaming: false,
        },
        assistantBase(action.assistantId),
      ];

    case "status":
      return patch(state, action.id, (it) => ({
        ...it,
        statusTrace: [...it.statusTrace, action.status],
      }));

    case "token":
      return patch(state, action.id, (it) => ({ ...it, content: it.content + action.text }));

    case "regenerating":
      // Retry: xoá token đã hiện của lượt này.
      return patch(state, action.id, (it) => ({ ...it, content: "" }));

    case "citations":
      return patch(state, action.id, (it) => ({ ...it, citations: action.citations }));

    case "visualization":
      return patch(state, action.id, (it) => ({
        ...it,
        visualization: action.visualization,
      }));

    case "clarification":
      return patch(state, action.id, (it) => ({
        ...it,
        clarificationNeeded: true,
        clarificationQuestion: action.question,
        content: action.question,
      }));

    case "blocked":
      return patch(state, action.id, (it) => ({ ...it, blocked: true }));

    case "error":
      return patch(state, action.id, (it) => ({ ...it, error: action.error }));

    case "debug":
      return patch(state, action.id, (it) => ({ ...it, debug: action.debug }));

    case "done":
      return patch(state, action.id, (it) => ({
        ...it,
        streaming: false,
        messageId: action.done.message_id,
        confidence: action.done.confidence,
        retrievalMode: action.done.retrieval_mode,
        warnings: action.done.warnings,
      }));

    default:
      return state;
  }
}
