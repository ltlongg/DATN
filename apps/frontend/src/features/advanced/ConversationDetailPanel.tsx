import { useState } from "react";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import type {
  MessageLogItem,
  MessageTokens,
  ConversationLogDetail as Detail,
} from "@/types/admin";

const nf = new Intl.NumberFormat("vi-VN");

// Raw task (lưu nguyên trong DB) -> nhãn tiếng Việt. Task lạ -> hiện raw (an toàn khi thêm task).
const TASK_LABELS: Record<string, string> = {
  build_query: "Dựng truy vấn",
  synthesize: "Tổng hợp",
  guardrail_input: "Kiểm duyệt",
};
const taskLabel = (t: string) => TASK_LABELS[t] ?? t;

function QualityFlags({ m }: { m: MessageLogItem }) {
  const flags: { label: string; on: boolean; cls: string }[] = [
    { label: "tin cậy thấp", on: m.quality.low_confidence, cls: "bg-orange-100 text-orange-800" },
    { label: "thiếu citation", on: m.quality.no_citation, cls: "bg-rose-100 text-rose-800" },
    { label: "cần làm rõ", on: m.quality.clarification, cls: "bg-amber-100 text-amber-800" },
    { label: "có cảnh báo", on: m.quality.has_warning, cls: "bg-yellow-100 text-yellow-800" },
  ];
  const active = flags.filter((f) => f.on);
  if (active.length === 0)
    return <span className="text-[11px] text-green-700">không có cảnh báo</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {active.map((f) => (
        <span key={f.label} className={`rounded-full px-2 py-0.5 text-[11px] ${f.cls}`}>
          {f.label}
        </span>
      ))}
    </div>
  );
}

function TokenBreakdown({ tokens }: { tokens: MessageTokens }) {
  return (
    <div className="rounded-md border border-paper-border bg-paper/60 p-2 text-[11px] text-ink-soft">
      <p className="mb-1 font-medium text-ink">Tổng: {nf.format(tokens.total_tokens)} token</p>
      <table className="w-full">
        <tbody>
          {tokens.rows.map((r) => (
            <tr key={`${r.task}-${r.model}`}>
              <td className="pr-2 text-ink">{taskLabel(r.task)}</td>
              <td className="pr-2">{r.model}</td>
              <td className="pr-2 text-right">
                {nf.format(r.prompt_tokens)}/{nf.format(r.completion_tokens)}
              </td>
              <td className="text-right font-medium text-ink">{nf.format(r.total_tokens)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

type TabKey = "quality" | "token";

/** Cột phải: panel chi tiết phiên đang chọn, 2 tab Chất lượng / Token (song song, giữ cả hai). */
export function ConversationDetailPanel({
  detail,
  tokensByMessage,
}: {
  detail: Detail;
  tokensByMessage: Map<string, MessageTokens>;
}) {
  const [tab, setTab] = useState<TabKey>("quality");
  const assistants = detail.messages.filter((m) => m.role === "assistant");

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex gap-1 border-b border-paper-border">
        {(["quality", "token"] as TabKey[]).map((k) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`border-b-2 px-3 py-1.5 text-sm ${
              tab === k
                ? "border-brand font-medium text-brand"
                : "border-transparent text-ink-soft hover:text-ink"
            }`}
          >
            {k === "quality" ? "Chất lượng" : "Token"}
          </button>
        ))}
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto">
        {assistants.length === 0 ? (
          <p className="text-sm text-ink-soft">
            Chưa có câu trả lời nào được lưu (hội thoại lỗi/bị chặn giữa chừng).
          </p>
        ) : (
          assistants.map((m, i) => (
            <div key={m.id} className="space-y-1">
              <p className="flex items-center gap-2 text-xs font-medium text-ink">
                Lượt {i + 1}
                <ConfidenceBadge confidence={m.confidence} />
              </p>
              {tab === "quality" ? (
                <QualityFlags m={m} />
              ) : tokensByMessage.has(m.id) ? (
                <TokenBreakdown tokens={tokensByMessage.get(m.id) as MessageTokens} />
              ) : (
                <p className="text-[11px] text-ink-soft">Không có dữ liệu token.</p>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
