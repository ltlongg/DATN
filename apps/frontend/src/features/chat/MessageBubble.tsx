import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { Markdown } from "@/components/Markdown";
import { CitationList } from "@/features/chat/CitationList";
import { ClarificationPrompt } from "@/features/chat/ClarificationPrompt";
import { DebugPanel } from "@/features/chat/DebugPanel";
import { AssistantAvatar, UserAvatar } from "@/features/chat/MessageAvatar";
import type { ChatItem } from "@/features/chat/chatReducer";
import { formatTtft } from "@/lib/format";
import { useAuthStore } from "@/store/authStore";

/** Số từ của câu trả lời — tính tại chỗ từ content, không lưu DB. */
function countWords(text: string): number {
  const t = text.trim();
  return t === "" ? 0 : t.split(/\s+/).length;
}

/** 1 dòng chat. User: bong bóng phải. Assistant: khối trái + citations/confidence/lỗi. */
export function MessageBubble({
  item,
  onReply,
}: {
  item: ChatItem;
  onReply: (text: string) => void;
}) {
  const isAdmin = useAuthStore((s) => s.user?.role === "admin");
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
        ) : item.clarificationNeeded ? (
          <ClarificationPrompt
            question={item.clarificationQuestion ?? item.content}
            disabled={item.streaming}
            onReply={onReply}
          />
        ) : (
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

            {!item.streaming && (
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <ConfidenceBadge confidence={item.confidence} />
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
                {item.warnings.map((w, i) => (
                  <span key={i} className="text-xs text-amber-700">
                    {w}
                  </span>
                ))}
              </div>
            )}

            <CitationList citations={item.citations} />
          </>
        )}

        {isAdmin && <DebugPanel item={item} />}
      </div>
    </div>
  );
}
