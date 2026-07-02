import { formatDateTime } from "@/lib/format";
import type { MessageLogItem, ConversationLogDetail as Detail } from "@/types/admin";

function QualityFlags({ m }: { m: MessageLogItem }) {
  const flags: { label: string; on: boolean; cls: string }[] = [
    { label: "tin cậy thấp", on: m.quality.low_confidence, cls: "bg-orange-100 text-orange-800" },
    { label: "thiếu citation", on: m.quality.no_citation, cls: "bg-rose-100 text-rose-800" },
    { label: "cần làm rõ", on: m.quality.clarification, cls: "bg-amber-100 text-amber-800" },
    { label: "có cảnh báo", on: m.quality.has_warning, cls: "bg-yellow-100 text-yellow-800" },
  ];
  const active = flags.filter((f) => f.on);
  if (active.length === 0) return null;
  return (
    <div className="mt-1 flex flex-wrap gap-1">
      {active.map((f) => (
        <span key={f.label} className={`rounded-full px-2 py-0.5 text-[11px] ${f.cls}`}>
          {f.label}
        </span>
      ))}
    </div>
  );
}

/** Chi tiết 1 hội thoại: mọi message + cờ chất lượng (backend tính sẵn). Read-only. */
export function ConversationLogDetail({ detail }: { detail: Detail }) {
  return (
    <div className="space-y-1">
      <div className="border-b border-paper-border pb-2">
        <p className="font-medium text-ink">{detail.title}</p>
        <p className="text-xs text-ink-soft">
          {detail.user_name} · {detail.user_email} · {formatDateTime(detail.created_at)}
        </p>
      </div>
      <div className="max-h-[60vh] space-y-3 overflow-y-auto pt-2">
        {detail.messages.map((m) => (
          <div
            key={m.id}
            className={m.role === "user" ? "text-right" : "text-left"}
          >
            <div
              className={`inline-block max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                m.role === "user"
                  ? "bg-brand text-brand-fg"
                  : "border border-paper-border bg-paper-card text-ink"
              }`}
            >
              <p className="whitespace-pre-wrap">{m.content}</p>
              {m.role === "assistant" && <QualityFlags m={m} />}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
