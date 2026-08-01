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
        <div className="flex flex-1 flex-col items-center justify-center gap-6 px-6 text-center">
          <div>
            <h2 className="text-xl font-semibold text-ink">Bắt đầu hỏi đáp lịch sử</h2>
            <p className="mt-1 text-sm text-ink-soft">
              Câu trả lời có căn cứ từ tài liệu, kèm nguồn trích dẫn.
            </p>
          </div>
          <div className="grid w-full max-w-xl gap-2 sm:grid-cols-2">
            {SAMPLE_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => onSend(q)}
                className="rounded-lg border border-paper-border bg-paper-card px-4 py-3 text-left text-sm text-ink transition hover:border-brand"
              >
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
