import { useState, type KeyboardEvent } from "react";

/**
 * Ô nhập câu hỏi. Enter gửi, Shift+Enter xuống dòng. Khoá khi đang stream.
 *
 * KHÔNG còn ô chọn cách truy hồi: agent tự chọn traditional/hybrid theo câu hỏi (bậc B2,
 * `docs/plan/agentic-retrieval-loop-plan.md` §0.1). Bắt giáo viên chọn "Vector" hay "Kết hợp"
 * là bắt họ biết nội tạng hệ thống. Override vẫn còn ở TẦNG API (`AskRequest.mode`) để so
 * traditional/graph/hybrid trên cùng một câu lúc đánh giá — chỉ không hiện ra UI.
 */
const DEFAULT_PLACEHOLDER = "Hỏi về lịch sử Việt Nam…";

export function Composer({
  disabled,
  onSend,
  placeholder = DEFAULT_PLACEHOLDER,
}: {
  disabled: boolean;
  onSend: (text: string) => void;
  /** Đổi khi agent đang chờ câu làm rõ — đây là thứ THAY cho ô nhập riêng trong khối
   *  clarification, nên nó phải dẫn được mắt xuống đây. */
  placeholder?: string;
}) {
  const [text, setText] = useState("");

  function send() {
    const t = text.trim();
    if (!t || disabled) return;
    onSend(t);
    setText("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  }

  return (
    <div className="border-t border-paper-border bg-paper-card p-3">
      <div className="flex items-end gap-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder={placeholder}
          className="max-h-40 flex-1 resize-none rounded-lg border border-paper-border bg-white px-3 py-2 outline-none focus:border-brand"
        />
        <button
          onClick={send}
          disabled={disabled || text.trim() === ""}
          className="rounded-lg bg-brand px-4 py-2 font-medium text-brand-fg disabled:opacity-60"
        >
          Gửi
        </button>
      </div>
    </div>
  );
}
