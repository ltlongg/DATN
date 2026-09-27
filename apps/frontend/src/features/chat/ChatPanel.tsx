import { Lightbulb } from "lucide-react";
import { BrandMark } from "@/components/BrandMark";
import { Composer } from "@/features/chat/Composer";
import { MessageList } from "@/features/chat/MessageList";
import type { ChatItem } from "@/features/chat/chatReducer";

const SAMPLE_QUESTIONS = [
  "Vì sao thực dân Pháp nổ súng xâm lược Việt Nam năm 1858?",
  "Diễn biến chính của phong trào Cần Vương?",
  "Nguyễn Tất Thành ra đi tìm đường cứu nước năm nào?",
  "Ý nghĩa lịch sử của Cách mạng Tháng Tám 1945?",
];

/**
 * Lượt cuối là câu hỏi lại của agent -> ô nhập chính đổi lời mời. Chỉ xét item CUỐI: trả lời
 * xong một clarification rồi thì lời mời phải trở lại bình thường.
 */
function isAwaitingClarification(items: ChatItem[]): boolean {
  const last = items[items.length - 1];
  return !!last && last.role === "assistant" && last.clarificationNeeded;
}

/** Khung chat: empty-state gợi ý câu hỏi hoặc danh sách message, + ô nhập. */
export function ChatPanel({
  items,
  streaming,
  onSend,
}: {
  items: ChatItem[];
  streaming: boolean;
  onSend: (text: string) => void;
}) {
  return (
    <div className="flex h-full flex-col">
      {items.length === 0 ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-8 overflow-y-auto px-6 py-10 text-center">
          <div className="flex flex-col items-center">
            <BrandMark className="h-12 w-12 rounded-xl" />
            <h2 className="mt-5 text-2xl font-semibold text-ink">Xin chàoooooooo!</h2>
            <p className="mt-2 text-sm text-ink-soft">
              Bạn hỏi tự nhiên nhé, mình rất sẵn lòng trả lời. Hoặc thử một trong các câu hỏi mẫu dưới đây.
            </p>
          </div>
          <div className="grid w-full max-w-2xl gap-3 sm:grid-cols-2">
            {SAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => onSend(q)}
                className="card group flex items-start gap-3 p-4 text-left text-sm leading-relaxed text-ink transition hover:border-brand/40 hover:shadow-pop"
              >
                <Lightbulb
                  size={16}
                  className="mt-0.5 shrink-0 text-gold transition-colors group-hover:text-brand"
                  aria-hidden
                />
                {q}
              </button>
            ))}
          </div>
        </div>
      ) : (
        <MessageList items={items} />
      )}
      <Composer
        disabled={streaming}
        onSend={onSend}
        placeholder={
          isAwaitingClarification(items) ? "Trả lời để làm rõ…" : undefined
        }
      />
    </div>
  );
}
