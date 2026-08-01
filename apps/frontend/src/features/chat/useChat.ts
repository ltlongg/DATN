import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import {
  openAskStream,
  type AskHandlers,
  type AskStreamController,
} from "@/api/askStream";
import { chatReducer } from "@/features/chat/chatReducer";
import { useAuthStore } from "@/store/authStore";
import type { Message } from "@/types";

/**
 * Quản lý các dòng chat của 1 conversation + gửi câu hỏi qua SSE.
 *
 * Hook TỰ sở hữu `conversationId` (không nhận qua prop) để câu hỏi ĐẦU của phiên mới hiển
 * thị bubble user NGAY, không chờ round-trip tạo phiên: `ask` dispatch `startTurn` trước,
 * rồi mới `await createConversation()` (chạy nền) để lấy id trước khi mở stream.
 *
 * Abort stream chỉ khi unmount hoặc CHUYỂN PHIÊN tường minh (`selectConversation`/
 * `resetConversation`) — KHÔNG abort khi id null→mới do lazy-create.
 *
 * Debug chỉ bật cho admin (BE cũng ép false cho user). Hook KHÔNG đụng tới panel bản đồ:
 * AskPage tự mở panel theo DỮ LIỆU (viz mới, dù từ SSE hay từ phiên nạp lại từ DB).
 */
export function useChat() {
  const [items, dispatch] = useReducer(chatReducer, []);
  const [streaming, setStreaming] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const isAdmin = useAuthStore((s) => s.user?.role === "admin");
  const controllerRef = useRef<AskStreamController | null>(null);

  const buildHandlers = useCallback(
    (assistantId: string): AskHandlers => ({
      onSteps: (steps) => dispatch({ type: "steps", id: assistantId, steps }),
      onStep: (step) => dispatch({ type: "step", id: assistantId, step }),
      onToken: (t) => dispatch({ type: "token", id: assistantId, text: t }),
      onRegenerating: () => dispatch({ type: "regenerating", id: assistantId }),
      onCitations: (citations) => dispatch({ type: "citations", id: assistantId, citations }),
      onVisualization: (visualization) =>
        dispatch({ type: "visualization", id: assistantId, visualization }),
      onClarification: (question) =>
        dispatch({ type: "clarification", id: assistantId, question }),
      onBlocked: () => dispatch({ type: "blocked", id: assistantId }),
      onError: (error) => dispatch({ type: "error", id: assistantId, error }),
      onDone: (done) => dispatch({ type: "done", id: assistantId, done }),
    }),
    [],
  );

  /**
   * Gửi câu hỏi. `createConversation` chỉ được gọi khi CHƯA có phiên (câu đầu) để tạo lazy;
   * bubble user + placeholder assistant đã hiện TRƯỚC khi gọi nó.
   */
  const ask = useCallback(
    async (
      question: string,
      createConversation: () => Promise<string>,
    ) => {
      const text = question.trim();
      if (streaming || !text) return;
      const assistantId = crypto.randomUUID();
      // Optimistic: hiện bubble user + placeholder assistant NGAY, trước mọi network.
      dispatch({
        type: "startTurn",
        userId: crypto.randomUUID(),
        userText: text,
        assistantId,
        at: Date.now(),
      });
      setStreaming(true);

      let cid = conversationId;
      if (!cid) {
        try {
          cid = await createConversation();
        } catch {
          dispatch({
            type: "error",
            id: assistantId,
            error: { code: "conversation_error", message: "Không tạo được phiên trò chuyện." },
          });
          setStreaming(false);
          return;
        }
        setConversationId(cid);
      }

      const controller = openAskStream(
        cid,
        { question: text, debug: isAdmin },
        buildHandlers(assistantId),
      );
      controllerRef.current = controller;
      void controller.done.finally(() => setStreaming(false));
    },
    [conversationId, streaming, isAdmin, buildHandlers],
  );

  // Mở 1 phiên đã có: huỷ stream đang chạy, nạp lịch sử.
  const selectConversation = useCallback((id: string, messages: Message[]) => {
    controllerRef.current?.abort();
    setConversationId(id);
    dispatch({ type: "load", messages });
  }, []);

  // Bắt đầu phiên mới rỗng (id tạo lazy khi gửi câu đầu).
  const resetConversation = useCallback(() => {
    controllerRef.current?.abort();
    setConversationId(null);
    dispatch({ type: "load", messages: [] });
  }, []);

  // Huỷ stream đang chạy khi unmount.
  useEffect(() => () => controllerRef.current?.abort(), []);

  return { items, ask, streaming, conversationId, selectConversation, resetConversation };
}
