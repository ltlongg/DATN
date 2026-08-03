import { Markdown } from "@/components/Markdown";
import { CitationList } from "@/features/chat/CitationList";
import { AssistantAvatar, UserAvatar } from "@/features/chat/MessageAvatar";
import { ProgressPanel } from "@/features/chat/ProgressPanel";
import type { ChatItem } from "@/features/chat/chatReducer";
import { formatTtft } from "@/lib/format";
import { useAuthStore } from "@/store/authStore";

/** Số từ của câu trả lời — tính tại chỗ từ content, không lưu DB. */
function countWords(text: string): number {
  const t = text.trim();
  return t === "" ? 0 : t.split(/\s+/).length;
}

/** 1 dòng chat. User: bong bóng phải. Assistant: khối trái + citations/lỗi. */
export function MessageBubble({ item }: { item: ChatItem }) {
  // Không cần biết role ở đây nữa: tầng 2 của panel tiến trình chỉ hiện khi `step.internals`
  // CÓ MẶT, mà backend đã bóc field đó cho mọi lượt không phải admin-bật-debug. Một nguồn
  // sự thật, và là nguồn ở phía server.
  const userName = useAuthStore((s) => s.user?.name ?? "");

  if (item.role === "user") {
    return (
      <div className="flex justify-end gap-2">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-brand px-4 py-2 text-brand-fg">
          {item.content}
        </div>
        <UserAvatar name={userName} />
      </div>
    );
  }

  return (
    <div className="flex justify-start gap-2">
      <AssistantAvatar />
      <div className="min-w-0 flex-1 rounded-2xl rounded-bl-sm border border-paper-border bg-paper-card px-4 py-3">
        {/* Trên MỌI nhánh (kể cả lỗi/bị chặn): panel cho thấy hệ thống đã đi tới đâu rồi
            mới dừng — im lặng ở đúng lúc hỏng là thứ khó chịu nhất. */}
        <ProgressPanel
          steps={item.steps}
          startedAt={item.startedAt}
          streaming={item.streaming}
        />
        {item.error ? (
          <p className="text-sm text-rose-700">⚠ {item.error.message}</p>
        ) : item.blocked ? (
          // Guardrails chặn: ưu tiên hiện safe message (agent đã stream qua token). Chỉ khi
          // không có content mới rơi về câu cố định.
          item.content !== "" ? (
            <div className="text-ink">
              <Markdown content={item.content} />
            </div>
          ) : (
            <p className="text-sm text-rose-700">
              Câu hỏi bị chặn bởi bộ lọc an toàn.
            </p>
          )
        ) : (
          // Câu hỏi lại (route `ambiguous`) đi CHUNG nhánh này, không có khối vàng riêng:
          // nó là một câu trả lời như mọi câu khác, chỉ khác ở chỗ kết thúc bằng dấu hỏi.
          // `content` đã là chính câu hỏi lại (reducer set từ event `clarification`).
          // CitationList tự ẩn khi rỗng nên không cần rẽ nhánh.
          <>
            <div className="text-ink">
              {item.content !== "" && <Markdown content={item.content} />}
              {item.streaming && item.content === "" && (
                <span className="text-ink-soft">Đang suy nghĩ…</span>
              )}
              {item.streaming && item.content !== "" && (
                <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-ink-soft align-middle" />
              )}
            </div>

            {/* `confidence` và `warnings` VẪN về đủ trong item (và vẫn lưu DB), chỉ không
                render ở đây: cả hai là ngôn ngữ nội bộ của orchestrator ("bỏ resolve của
                bước không có bước sau dùng tới") — người dùng đọc không hiểu, mà đọc rồi
                lại tưởng câu trả lời có vấn đề. Chỗ xem chúng là trang quản trị
                (`features/advanced`), nơi có ngữ cảnh để hiểu. */}
            {!item.streaming && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                {item.ttftMs !== null && (
                  <span
                    className="text-xs text-ink-soft"
                    title="Thời gian chờ tới chữ đầu tiên (gồm truy hồi + LLM)"
                  >
                    ⏱ {formatTtft(item.ttftMs)}
                  </span>
                )}
                <span className="text-xs text-ink-soft">
                  {countWords(item.content)} từ
                </span>
              </div>
            )}

            <CitationList citations={item.citations} />
          </>
        )}
      </div>
    </div>
  );
}
