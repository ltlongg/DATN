import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { Markdown } from "@/components/Markdown";
import { CitationList } from "@/features/chat/CitationList";
import { ClarificationPrompt } from "@/features/chat/ClarificationPrompt";
import { DebugPanel } from "@/features/chat/DebugPanel";
import type { ChatItem } from "@/features/chat/chatReducer";
import { useAuthStore } from "@/store/authStore";

/** 1 dòng chat. User: bong bóng phải. Assistant: khối trái + citations/confidence/lỗi. */
export function MessageBubble({
  item,
  onReply,
}: {
  item: ChatItem;
  onReply: (text: string) => void;
}) {
  const isAdmin = useAuthStore((s) => s.user?.role === "admin");

  if (item.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-brand px-4 py-2 text-brand-fg">
          {item.content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="w-full max-w-[95%] rounded-2xl rounded-bl-sm border border-paper-border bg-paper-card px-4 py-3">
        {item.error ? (
          <p className="text-sm text-rose-700">⚠ {item.error.message}</p>
        ) : item.blocked ? (
          <p className="text-sm text-rose-700">
            Câu hỏi bị chặn bởi bộ lọc an toàn.
          </p>
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
