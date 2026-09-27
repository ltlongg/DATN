import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { Markdown } from "@/components/Markdown";
import { ProgressPanel } from "@/features/chat/ProgressPanel";
import { formatDateTime, formatTtft } from "@/lib/format";
import type { ConversationLogDetail as Detail, MessageLogItem } from "@/types/admin";

// Nhóm vi phạm guardrails (agent-service schemas/guardrails.py) -> nhãn tiếng Việt. Nhóm lạ
// -> hiện raw.
const CATEGORY_LABELS: Record<string, string> = {
  prompt_injection: "Cố can thiệp hệ thống",
  harmful_instructions: "Hướng dẫn gây hại",
  self_harm: "Tự gây hại",
  illegal_activity: "Hoạt động phạm pháp",
  sexual_content: "Nội dung tình dục",
  hate_harassment: "Thù ghét, quấy rối",
  privacy_secret: "Moi thông tin riêng tư",
  other: "Vi phạm khác",
};

function HiddenContent() {
  return (
    <p className="italic text-ink-soft">Nội dung được ẩn để bảo vệ quyền riêng tư</p>
  );
}

function UserMessage({ m }: { m: MessageLogItem }) {
  if (m.visibility === "hidden") {
    return (
      <div className="text-right">
        <div className="inline-block max-w-[85%] rounded-lg bg-paper px-3 py-2 text-left text-sm">
          <HiddenContent />
        </div>
      </div>
    );
  }
  return (
    <div className="text-right">
      {m.flagged && (
        <div className="mb-1 flex flex-wrap justify-end gap-1">
          {m.flag_categories.map((c) => (
            <span key={c} className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] text-rose-800">
              {CATEGORY_LABELS[c] ?? c}
            </span>
          ))}
        </div>
      )}
      <div
        className={`inline-block max-w-[85%] rounded-lg bg-brand px-3 py-2 text-left text-sm text-brand-fg ${
          m.flagged ? "ring-2 ring-rose-500" : ""
        }`}
      >
        <p className="whitespace-pre-wrap">{m.content}</p>
      </div>
    </div>
  );
}

function AssistantMessage({ m }: { m: MessageLogItem }) {
  return (
    <div className="text-left">
      <div className="mb-0.5 flex items-center gap-2 text-[11px] text-ink-soft">
        <span>AI</span>
        <ConfidenceBadge confidence={m.confidence} />
        {m.ttft_ms !== null && (
          <span title="TTFT: từ lúc user hỏi tới chữ đầu tiên">⏱ {formatTtft(m.ttft_ms)}</span>
        )}
      </div>
      <div className="inline-block max-w-[92%] rounded-lg border border-paper-border bg-paper-card px-3 py-2 text-sm text-ink">
        {m.visibility === "hidden" ? (
          <HiddenContent />
        ) : (
          <>
            {/* startedAt=null -> panel bỏ phần thời gian (đo client-side, không dựng lại
                được sau khi phiên đã đóng); streaming=false -> tự gập ngay. */}
            <ProgressPanel steps={m.steps ?? []} startedAt={null} streaming={false} />
            <Markdown content={m.content ?? ""} />
          </>
        )}
      </div>
    </div>
  );
}

/** Cột giữa: replay hội thoại inline — bong bóng user (phải) + assistant (trái, render markdown
 * + badge độ tin cậy). Phần chất lượng/token nằm ở panel bên phải, không lẫn vào replay.
 *
 * Quyền riêng tư do backend quyết: message `hidden` không có nội dung (chỉ còn số liệu), danh
 * tính chỉ có khi hội thoại có tin bị gắn cờ vi phạm. Với message được xem, panel tiến trình
 * gập sẵn là chỗ DUY NHẤT xem lại luồng xử lý của hội thoại đã đóng. */
export function ConversationReplay({ detail }: { detail: Detail }) {
  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-paper-border pb-2">
        <p className="font-medium text-ink">
          {detail.title ?? <span className="italic text-ink-soft">Tiêu đề được ẩn</span>}
        </p>
        <p className="flex flex-wrap items-center gap-x-1 text-xs text-ink-soft">
          {detail.user_email ? (
            <>
              {detail.user_name} · {detail.user_email}
              <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] text-rose-800">
                Hiện danh tính do vi phạm
              </span>
            </>
          ) : (
            detail.user_anon_id
          )}{" "}
          · {formatDateTime(detail.created_at)}
          {detail.shared && (
            <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] text-emerald-800">
              Người dùng đã chia sẻ
            </span>
          )}
        </p>
      </div>

      <div className="mt-3 flex-1 space-y-3 overflow-y-auto">
        {detail.messages.map((m) =>
          m.role === "user" ? (
            <UserMessage key={m.id} m={m} />
          ) : (
            <AssistantMessage key={m.id} m={m} />
          ),
        )}
      </div>
    </div>
  );
}
