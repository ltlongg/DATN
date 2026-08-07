import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";
import { Mic, Square } from "lucide-react";
import { joinText, useSpeechRecognition } from "@/features/chat/useSpeechRecognition";

/**
 * Ô nhập câu hỏi. Enter gửi, Shift+Enter xuống dòng. Khoá khi đang stream.
 *
 * KHÔNG còn ô chọn cách truy hồi: agent tự chọn traditional/hybrid theo câu hỏi (bậc B2,
 * `docs/plan/agentic-retrieval-loop-plan.md` §0.1). Bắt giáo viên chọn "Vector" hay "Kết hợp"
 * là bắt họ biết nội tạng hệ thống. Override vẫn còn ở TẦNG API (`AskRequest.mode`) để so
 * traditional/hybrid trên cùng một câu lúc đánh giá — chỉ không hiện ra UI.
 *
 * Nút mic đọc chính tả tiếng Việt (`docs/plan/voice-input-webspeech-plan.md`): chữ đổ thẳng vào
 * ô nhập để người dùng xem/sửa rồi tự bấm Gửi — KHÔNG tự gửi, vì nhận sai mà gửi luôn thì không
 * còn đường lùi.
 */
const DEFAULT_PLACEHOLDER = "Hỏi về lịch sử Việt Nam…";
const MAX_COMPOSER_HEIGHT_PX = 160;

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
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const {
    supported: micSupported,
    listening,
    transcript,
    error: micError,
    start: startMic,
    stop: stopMic,
  } = useSpeechRecognition();
  /** Phần người dùng đã gõ trước khi bấm mic — chữ đọc ra nối vào SAU nó, không đè lên. */
  const baseTextRef = useRef("");

  useLayoutEffect(() => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    // Thu nhỏ trước khi đo để ô nhập co lại khi người dùng xoá bớt nội dung.
    textarea.style.height = "auto";
    textarea.style.height = `${Math.min(textarea.scrollHeight, MAX_COMPOSER_HEIGHT_PX)}px`;
    textarea.style.overflowY =
      textarea.scrollHeight > MAX_COMPOSER_HEIGHT_PX ? "auto" : "hidden";
  }, [text]);

  useEffect(() => {
    if (!transcript) return;
    setText(joinText(baseTextRef.current, transcript));
  }, [transcript]);

  // Bấm câu hỏi mẫu ở empty-state trong lúc mic đang mở -> khoá ô nhập mà mic vẫn nóng.
  useEffect(() => {
    if (disabled && listening) stopMic();
  }, [disabled, listening, stopMic]);

  function toggleMic() {
    if (listening) {
      stopMic();
      return;
    }
    baseTextRef.current = text;
    startMic();
  }

  function send() {
    const t = text.trim();
    if (!t || disabled || listening) return;
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
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          rows={1}
          readOnly={listening}
          placeholder={placeholder}
          className="max-h-40 flex-1 resize-none rounded-lg border border-paper-border bg-white px-3 py-2 outline-none focus:border-brand"
        />
        {micSupported && (
          <button
            onClick={toggleMic}
            disabled={disabled}
            aria-label={listening ? "Dừng nói" : "Nói"}
            aria-pressed={listening}
            className={`flex h-[42px] w-[42px] items-center justify-center rounded-lg border transition disabled:cursor-not-allowed disabled:opacity-50 ${
              listening
                ? "animate-pulse border-brand bg-brand text-brand-fg"
                : "border-paper-border text-ink-soft hover:border-brand hover:text-brand"
            }`}
          >
            {listening ? <Square size={16} /> : <Mic size={16} />}
          </button>
        )}
        <button
          onClick={send}
          disabled={disabled || listening || text.trim() === ""}
          className="rounded-lg bg-brand px-4 py-2 font-medium text-brand-fg disabled:opacity-60"
        >
          Gửi
        </button>
      </div>
      {micError && (
        <p role="alert" className="mt-2 text-sm text-brand">
          {micError}
        </p>
      )}
    </div>
  );
}
