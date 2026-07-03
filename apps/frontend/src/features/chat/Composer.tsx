import { useState, type KeyboardEvent } from "react";
import type { RetrievalMode } from "@/api/askStream";

const MODE_OPTIONS: { value: RetrievalMode; label: string }[] = [
  { value: "hybrid", label: "Kết hợp" },
  { value: "traditional", label: "Vector" },
  { value: "graph", label: "Đồ thị" },
];

/** Ô nhập câu hỏi. Enter gửi, Shift+Enter xuống dòng. Khoá khi đang stream. */
export function Composer({
  disabled,
  mode,
  onModeChange,
  onSend,
}: {
  disabled: boolean;
  mode: RetrievalMode;
  onModeChange: (mode: RetrievalMode) => void;
  onSend: (text: string) => void;
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
      <div className="mb-2 flex items-center gap-2">
        <label htmlFor="retrieval-mode" className="text-xs text-ink-soft">
          Cách truy hồi
        </label>
        <select
          id="retrieval-mode"
          value={mode}
          onChange={(e) => onModeChange(e.target.value as RetrievalMode)}
          className="rounded-md border border-paper-border bg-white px-2 py-1 text-xs text-ink outline-none focus:border-brand"
        >
          {MODE_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
      <div className="flex items-end gap-2">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder="Hỏi về lịch sử Việt Nam…"
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
