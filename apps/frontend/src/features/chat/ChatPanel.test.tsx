// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import "@testing-library/jest-dom/vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "@/features/chat/ChatPanel";
import type { ChatItem } from "@/features/chat/chatReducer";

// jsdom không implement scrollIntoView, mà MessageList gọi nó mỗi lần items đổi.
Element.prototype.scrollIntoView = vi.fn();

afterEach(cleanup);

function item(partial: Partial<ChatItem> & Pick<ChatItem, "id" | "role">): ChatItem {
  return {
    messageId: null,
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
    streaming: false,
    ...partial,
  };
}

const ASKED = item({ id: "u1", role: "user", content: "Lập trường của Pháp ở hiệp định?" });
const CLARIFY = item({
  id: "a1",
  role: "assistant",
  clarificationNeeded: true,
  content: "Bạn hỏi về hiệp định nào ạ?",
});
const ANSWERED = item({ id: "a2", role: "assistant", content: "Hiệp định Genève..." });

describe("ChatPanel — trả lời câu hỏi lại", () => {
  it("câu hỏi lại render như câu trả lời thường, KHÔNG có ô nhập riêng", () => {
    // Ô nhập cũ trong khối clarification gọi đúng cùng `onSend` với Composer -> hai ô làm
    // một việc, mà ô chính lại không khoá nên không có gì cho biết chúng tương đương.
    render(<ChatPanel items={[ASKED, CLARIFY]} streaming={false} onSend={vi.fn()} />);
    expect(screen.getByText("Bạn hỏi về hiệp định nào ạ?")).toBeInTheDocument();
    expect(screen.getAllByRole("textbox")).toHaveLength(1); // đúng một: Composer
    expect(screen.getAllByRole("button", { name: "Gửi" })).toHaveLength(1);
  });

  it("đang chờ làm rõ thì ô nhập chính đổi lời mời", () => {
    render(<ChatPanel items={[ASKED, CLARIFY]} streaming={false} onSend={vi.fn()} />);
    expect(screen.getByPlaceholderText("Trả lời để làm rõ…")).toBeInTheDocument();
  });

  it("trả lời xong thì lời mời trở lại bình thường", () => {
    // Chỉ xét item CUỐI — không thì hội thoại từng có clarification sẽ kẹt lời mời đó mãi.
    render(
      <ChatPanel items={[ASKED, CLARIFY, ANSWERED]} streaming={false} onSend={vi.fn()} />,
    );
    expect(screen.getByPlaceholderText("Hỏi về lịch sử Việt Nam…")).toBeInTheDocument();
  });

  it("gõ vào ô chính gửi được câu làm rõ", async () => {
    const onSend = vi.fn();
    render(<ChatPanel items={[ASKED, CLARIFY]} streaming={false} onSend={onSend} />);
    await userEvent.type(screen.getByRole("textbox"), "Hiệp định Genève 1954");
    await userEvent.click(screen.getByRole("button", { name: "Gửi" }));
    expect(onSend).toHaveBeenCalledWith("Hiệp định Genève 1954");
  });
});
