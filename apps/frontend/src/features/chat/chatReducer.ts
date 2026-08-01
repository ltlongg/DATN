import type { DonePayload, StepDeclaration, StepUpdate } from "@/api/askStream";
import type { Citation, Message, ProgressStep, VisualizationPayload } from "@/types";

/**
 * Dòng "Phân tích câu hỏi" là dòng DUY NHẤT frontend tự sinh (plan §7.3.1 mục 2): lúc mở
 * stream chưa biết kịch bản nên chưa có gì để agent emit, mà để trống thì người dùng nhìn
 * như hệ thống đứng hình. Agent vẫn khai báo lại đúng id này trong event `steps` — merge
 * giữ nguyên state đang chạy, nên không nháy.
 */
const PLAN_STEP_ID = "plan";
const PLAN_STEP_LABEL = "Phân tích câu hỏi";

function initialSteps(): ProgressStep[] {
  return [{ id: PLAN_STEP_ID, label: PLAN_STEP_LABEL, kind: "system", state: "running" }];
}

/**
 * Agent gửi danh sách (id/label/kind) tách khỏi state (event `step`). Merge phải GIỮ
 * state/detail của id đã có — nếu không, dòng `plan` đang `running` bị đạp về `pending`
 * rồi mới `done`, tức nháy ngược một nhịp.
 */
function mergeDeclaration(
  prev: ProgressStep[],
  declaration: StepDeclaration[],
): ProgressStep[] {
  const byId = new Map(prev.map((s) => [s.id, s]));
  return declaration.map((d) => {
    const old = byId.get(d.id);
    // `internals` cũng phải mang theo, cùng lý do với `detail`: danh sách phát lại chỉ có
    // id/label/kind, bỏ qua là tầng 2 của mọi bước đã xong bị xoá trắng khi soạn lại.
    return {
      ...d,
      state: old?.state ?? "pending",
      detail: old?.detail,
      internals: old?.internals,
    };
  });
}

/**
 * Stream đóng -> dòng còn `running` sẽ không bao giờ có kết (lỗi, abort, node chết giữa
 * chừng) nên hạ xuống `partial` (plan §7.3.1 mục 5). `pending` GIỮ NGUYÊN: nó mang nghĩa
 * "bước này không chạy", khác hẳn "chạy dở". Trùng luật với `SseCollector._closed_steps`
 * bên backend để bản đang xem và bản lưu lại khớp nhau.
 */
function closeOutSteps(steps: ProgressStep[]): ProgressStep[] {
  return steps.map((s) => (s.state === "running" ? { ...s, state: "partial" } : s));
}

/** Model hiển thị 1 dòng chat (user hoặc assistant). Assistant gom dần theo SSE. */
export interface ChatItem {
  id: string; // React key ổn định (assistantId lúc stream / message.id khi load lại)
  messageId: string | null; // id đã persist (từ event done); null khi chưa lưu
  role: "user" | "assistant";
  content: string;
  /** Panel tiến trình (B3). Rỗng với message user; message cũ chưa có B3 cũng rỗng. */
  steps: ProgressStep[];
  /**
   * Mốc bắt đầu lượt (ms, `Date.now()` do caller truyền vào để reducer thuần). null với
   * message nạp từ DB — thời gian đo client-side nên KHÔNG dựng lại được sau reload; V1
   * chấp nhận reload thấy đủ bước nhưng không có thời gian (plan §7.3).
   */
  startedAt: number | null;
  citations: Citation[];
  visualization: VisualizationPayload | null;
  /**
   * Route `ambiguous` — agent hỏi lại thay vì trả lời. Câu hỏi lại nằm luôn trong `content`
   * (render y như câu trả lời thường); cờ này chỉ còn để `ChatPanel` đổi placeholder ô nhập.
   */
  clarificationNeeded: boolean;
  confidence: string | null;
  retrievalMode: string | null;
  warnings: string[];
  /** TTFT (ms) từ event done / message đã lưu; null khi chưa xong hoặc không đo được. */
  ttftMs: number | null;
  error: { code: string; message: string } | null;
  blocked: boolean;
  streaming: boolean;
}

export type ChatAction =
  | { type: "load"; messages: Message[] }
  | {
      type: "startTurn";
      userId: string;
      userText: string;
      assistantId: string;
      /** `Date.now()` truyền từ caller — reducer phải thuần để test được. */
      at: number;
    }
  | { type: "steps"; id: string; steps: StepDeclaration[] }
  | { type: "step"; id: string; step: StepUpdate }
  | { type: "token"; id: string; text: string }
  | { type: "regenerating"; id: string }
  | { type: "citations"; id: string; citations: Citation[] }
  | { type: "visualization"; id: string; visualization: VisualizationPayload | null }
  | { type: "clarification"; id: string; question: string }
  | { type: "blocked"; id: string }
  | { type: "error"; id: string; error: { code: string; message: string } }
  | { type: "done"; id: string; done: DonePayload };

function assistantBase(id: string): ChatItem {
  return {
    id,
    messageId: null,
    role: "assistant",
    content: "",
    steps: [],
    startedAt: null,
    citations: [],
    visualization: null,
    clarificationNeeded: false,
    confidence: null,
    retrievalMode: null,
    warnings: [],
    ttftMs: null,
    error: null,
    blocked: false,
    streaming: true,
  };
}

/**
 * Message đã persist -> ChatItem. `steps` mang theo cả `internals` đã lưu, nên reload/mở lại
 * hội thoại cũ vẫn xem được tầng 2 — khác hẳn DebugPanel cũ (ephemeral, mất sạch sau F5).
 */
export function messageToItem(m: Message): ChatItem {
  return {
    id: m.id,
    messageId: m.id,
    role: m.role,
    content: m.content,
    // `?? []` phòng message lưu trước khi có cột `steps` (API trả mảng rỗng, nhưng dữ liệu
    // cũ trong cache/mock có thể thiếu hẳn field).
    steps: m.steps ?? [],
    startedAt: null,
    citations: m.citations,
    visualization: m.visualization,
    clarificationNeeded: m.clarification_needed,
    confidence: m.confidence,
    retrievalMode: m.retrieval_mode,
    warnings: m.warnings,
    ttftMs: m.ttft_ms,
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
        { ...assistantBase(action.assistantId), steps: initialSteps(), startedAt: action.at },
      ];

    case "steps":
      return patch(state, action.id, (it) => ({
        ...it,
        steps: mergeDeclaration(it.steps, action.steps),
      }));

    case "step":
      // id không có trong danh sách -> không dòng nào khớp -> bỏ qua, KHÔNG mọc dòng ma.
      return patch(state, action.id, (it) => ({
        ...it,
        steps: it.steps.map((s) =>
          s.id === action.step.id
            ? {
                ...s,
                state: action.step.state,
                ...(action.step.detail !== undefined ? { detail: action.step.detail } : {}),
                ...(action.step.internals !== undefined
                  ? { internals: action.step.internals }
                  : {}),
              }
            : s,
        ),
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
      // Câu hỏi lại vào thẳng `content` — nó được render y như câu trả lời thường, nên giữ
      // thêm một bản sao trong field riêng chỉ tạo cơ hội cho hai chỗ lệch nhau.
      return patch(state, action.id, (it) => ({
        ...it,
        clarificationNeeded: true,
        content: action.question,
      }));

    case "blocked":
      // Guardrails chặn input: agent KHÔNG gửi done -> tự kết thúc lượt (tắt streaming) để
      // bong bóng thôi hiện con trỏ nhấp nháy. Safe message đã nằm trong content qua token.
      return patch(state, action.id, (it) => ({
        ...it,
        blocked: true,
        streaming: false,
        steps: closeOutSteps(it.steps),
      }));

    case "error":
      // `streaming: false` — lượt này đã kết thúc. Trước B3 field đó bị bỏ lại `true` vĩnh
      // viễn ở nhánh lỗi; không ai nhận ra vì bong bóng lỗi che hết phần phụ thuộc nó.
      return patch(state, action.id, (it) => ({
        ...it,
        error: action.error,
        streaming: false,
        steps: closeOutSteps(it.steps),
      }));

    case "done":
      return patch(state, action.id, (it) => ({
        ...it,
        streaming: false,
        steps: closeOutSteps(it.steps),
        messageId: action.done.message_id,
        confidence: action.done.confidence,
        retrievalMode: action.done.retrieval_mode,
        warnings: action.done.warnings,
        ttftMs: action.done.ttft_ms,
      }));

    default:
      return state;
  }
}
