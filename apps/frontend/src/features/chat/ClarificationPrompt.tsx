import { useState, type FormEvent } from "react";

/** Agent hỏi lại (route ambiguous). Trả lời nhanh -> gửi tiếp, backend giữ history. */
export function ClarificationPrompt({
  question,
  disabled,
  onReply,
}: {
  question: string;
  disabled: boolean;
  onReply: (text: string) => void;
}) {
  const [text, setText] = useState("");

  function submit(e: FormEvent) {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;
    onReply(t);
    setText("");
  }

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
      <p className="text-sm text-amber-900">{question}</p>
      <form onSubmit={submit} className="mt-2 flex gap-2">
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={disabled}
          placeholder="Trả lời để làm rõ…"
          className="flex-1 rounded-md border border-amber-200 bg-white px-3 py-1.5 text-sm outline-none focus:border-brand"
        />
        <button
          type="submit"
          disabled={disabled}
          className="rounded-md bg-brand px-3 py-1.5 text-sm text-brand-fg disabled:opacity-60"
        >
          Gửi
        </button>
      </form>
    </div>
  );
}
