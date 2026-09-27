import { Clock } from "lucide-react";
import { Alert } from "@/components/Alert";
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
      <div className="flex justify-end gap-3">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-tr-md bg-brand px-4 py-2.5 leading-relaxed text-brand-fg shadow-sm">
          {item.content}
        </div>
        <UserAvatar name={userName} />
      </div>
    );
  }

  return (
    <div className="flex justify-start gap-3">
      <AssistantAvatar />
      <div className="min-w-0 flex-1 rounded-2xl rounded-tl-md border border-paper-border bg-paper-card px-5 py-4 shadow-card">
        {/* Trên MỌI nhánh (kể cả lỗi/bị chặn): panel cho thấy hệ thống đã đi tới đâu rồi
            mới dừng — im lặng ở đúng lúc hỏng là thứ khó chịu nhất. */}
        <ProgressPanel
          steps={item.steps}
          startedAt={item.startedAt}
          streaming={item.streaming}
        />
        {item.error ? (
          <Alert>{item.error.message}</Alert>
        ) : item.blocked ? (
          // Guardrails chặn: ưu tiên hiện safe message (agent đã stream qua token). Chỉ khi
          // không có content mới rơi về câu cố định.
          item.content !== "" ? (
            <div className="text-ink">
              <Markdown content={item.content} />
            </div>
          ) : (
            <Alert tone="warning">Câu hỏi bị chặn bởi bộ lọc an toàn.</Alert>
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
                <span className="inline-flex items-center gap-2 text-sm text-ink-soft">
                  <span className="flex gap-1" aria-hidden>
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand/70 [animation-delay:-0.3s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand/70 [animation-delay:-0.15s]" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-brand/70" />
                  </span>
                  Đang suy nghĩ…
                </span>
              )}
              {item.streaming && item.content !== "" && (
                <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse rounded-sm bg-brand/60 align-middle" />
              )}
            </div>

            {/* `confidence` và `warnings` VẪN về đủ trong item (và vẫn lưu DB), chỉ không
                render ở đây: cả hai là ngôn ngữ nội bộ của orchestrator ("bỏ resolve của
                bước không có bước sau dùng tới") — người dùng đọc không hiểu, mà đọc rồi
                lại tưởng câu trả lời có vấn đề. Chỗ xem chúng là trang quản trị
                (`features/advanced`), nơi có ngữ cảnh để hiểu. */}
            {!item.streaming && (
              <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-ink-faint">
                {item.ttftMs !== null && (
                  <span
                    className="inline-flex items-center gap-1"
                    title="Thời gian chờ tới chữ đầu tiên (gồm truy hồi + LLM)"
                  >
                    <Clock size={12} aria-hidden />
                    {formatTtft(item.ttftMs)}
                  </span>
                )}
                <span>{countWords(item.content)} từ</span>
              </div>
            )}

            <CitationList citations={item.citations} />
          </>
        )}
      </div>
    </div>
  );
}
