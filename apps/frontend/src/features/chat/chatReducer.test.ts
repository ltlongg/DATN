import { describe, it, expect } from "vitest";
import { chatReducer, type ChatItem } from "@/features/chat/chatReducer";

/** Dựng state có 1 bong bóng assistant đang stream với id cho trước. */
function startState(assistantId: string): ChatItem[] {
  return chatReducer([], {
    type: "startTurn",
    userId: "u1",
    userText: "câu hỏi",
    assistantId,
  });
}

describe("chatReducer — guardrails blocked", () => {
  it("giữ safe message ở content và set blocked=true khi token rồi blocked", () => {
    const id = "a1";
    let state = startState(id);
    // Agent stream safe message qua token TRƯỚC, rồi blocked.
    state = chatReducer(state, { type: "token", id, text: "Xin lỗi, mình không hỗ trợ " });
    state = chatReducer(state, { type: "token", id, text: "yêu cầu này." });
    state = chatReducer(state, { type: "blocked", id });

    const assistant = state.find((it) => it.id === id)!;
    expect(assistant.blocked).toBe(true);
    // Content KHÔNG bị thay bằng câu cố định — vẫn là safe message đã stream.
    expect(assistant.content).toBe("Xin lỗi, mình không hỗ trợ yêu cầu này.");
    // Blocked kết thúc lượt (agent không gửi done) -> streaming tắt để bỏ con trỏ nhấp nháy.
    expect(assistant.streaming).toBe(false);
  });

  it("blocked không có content vẫn set cờ blocked (bong bóng rơi về câu cố định ở UI)", () => {
    const id = "a2";
    let state = startState(id);
    state = chatReducer(state, { type: "blocked", id });

    const assistant = state.find((it) => it.id === id)!;
    expect(assistant.blocked).toBe(true);
    expect(assistant.content).toBe("");
    expect(assistant.streaming).toBe(false);
  });
});
