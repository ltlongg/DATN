import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { Markdown } from "@/components/Markdown";
import { ProgressPanel } from "@/features/chat/ProgressPanel";
import { formatDateTime, formatTtft } from "@/lib/format";
import type { ConversationLogDetail as Detail } from "@/types/admin";

/** Cột giữa: replay hội thoại inline — bong bóng user (phải) + assistant (trái, render markdown
 * + badge độ tin cậy). Phần chất lượng/token nằm ở panel bên phải, không lẫn vào replay.
 *
 * Panel tiến trình gập sẵn ở mỗi câu trả lời: đây là chỗ DUY NHẤT xem lại được luồng xử lý
 * của một hội thoại đã đóng (DebugPanel cũ realtime, F5 là mất). `internals` chỉ có ở đây vì
 * router /api/admin/logs gác admin. */
export function ConversationReplay({ detail }: { detail: Detail }) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-paper-border pb-2">
        <p className="font-medium text-ink">{detail.title}</p>
        <p className="text-xs text-ink-soft">
          {detail.user_name} · {detail.user_email} · {formatDateTime(detail.created_at)}
        </p>
      </div>

      <div className="mt-3 flex-1 space-y-3 overflow-y-auto">
        {detail.messages.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="text-right">
              <div className="inline-block max-w-[85%] rounded-lg bg-brand px-3 py-2 text-left text-sm text-brand-fg">
                <p className="whitespace-pre-wrap">{m.content}</p>
              </div>
            </div>
          ) : (
            <div key={m.id} className="text-left">
              <div className="mb-0.5 flex items-center gap-2 text-[11px] text-ink-soft">
                <span>AI</span>
                <ConfidenceBadge confidence={m.confidence} />
                {m.ttft_ms !== null && (
                  <span title="TTFT: từ lúc user hỏi tới chữ đầu tiên">
                    ⏱ {formatTtft(m.ttft_ms)}
                  </span>
                )}
              </div>
              <div className="inline-block max-w-[92%] rounded-lg border border-paper-border bg-paper-card px-3 py-2 text-sm text-ink">
                {/* startedAt=null -> panel bỏ phần thời gian (đo client-side, không dựng lại
                    được sau khi phiên đã đóng); streaming=false -> tự gập ngay. */}
                <ProgressPanel steps={m.steps ?? []} startedAt={null} streaming={false} />
                <Markdown content={m.content} />
              </div>
            </div>
          ),
        )}
      </div>
    </div>
  );
}
