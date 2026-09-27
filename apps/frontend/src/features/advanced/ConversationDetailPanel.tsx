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
  plan: "Dựng truy vấn",
  // Task cũ, giữ để log LỊCH SỬ (trước khi node đổi tên) vẫn có nhãn thay vì hiện raw.
  build_query: "Dựng truy vấn (cũ)",
  // Chỉ xuất hiện ở câu hỏi nhiều chặng -> phần lớn message KHÔNG có dòng này, và đó là
  // thông tin chứ không phải thiếu sót.
  resolve: "Trích mắt xích",
  synthesize: "Tổng hợp",
  guardrail_input: "Kiểm duyệt",
};
const taskLabel = (t: string) => TASK_LABELS[t] ?? t;

function QualityFlags({ m }: { m: MessageLogItem }) {
  const flags: { label: string; on: boolean; cls: string }[] = [
    { label: "tin cậy thấp", on: m.quality.low_confidence, cls: "badge-warning" },
    { label: "thiếu citation", on: m.quality.no_citation, cls: "badge-danger" },
    { label: "cần làm rõ", on: m.quality.clarification, cls: "badge-neutral" },
    { label: "có cảnh báo", on: m.quality.has_warning, cls: "badge-warning" },
  ];
  const active = flags.filter((f) => f.on);
  if (active.length === 0 && m.warnings.length === 0)
    return <span className="badge badge-success">không có cảnh báo</span>;
  return (
    <div className="space-y-1">
      {active.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {active.map((f) => (
            <span key={f.label} className={`badge ${f.cls}`}>
              {f.label}
            </span>
          ))}
        </div>
      )}
      {/* Nội dung warning chỉ hiện Ở ĐÂY, không hiện ở bong bóng chat (xem MessageBubble):
          đây là chẩn đoán nội bộ của orchestrator, admin mới có ngữ cảnh đọc. Badge "có
          cảnh báo" ở trên là cờ tổng hợp từ backend, giữ nguyên — danh sách dưới là chi
          tiết của chính cờ đó. */}
      {m.warnings.length > 0 && (
        <ul className="space-y-1 rounded-lg bg-amber-50 p-2.5 ring-1 ring-inset ring-amber-600/20">
          {m.warnings.map((w, i) => (
            <li key={i} className="text-xs leading-relaxed text-amber-800">
              • {String(w)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function TokenBreakdown({ tokens }: { tokens: MessageTokens }) {
  return (
    <div className="rounded-lg border border-paper-border bg-paper/60 p-2.5 text-xs text-ink-soft">
      <p className="mb-1.5 font-medium text-ink">Tổng: {nf.format(tokens.total_tokens)} token</p>
      <table className="w-full tabular-nums">
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
      <div className="mb-4 flex gap-1 border-b border-paper-border">
        {(["quality", "token"] as TabKey[]).map((k) => (
          <button
            key={k}
            onClick={() => setTab(k)}
            className={`-mb-px border-b-2 px-3 pb-2 text-sm transition-colors ${
              tab === k
                ? "border-brand font-medium text-brand"
                : "border-transparent text-ink-soft hover:text-ink"
            }`}
          >
            {k === "quality" ? "Chất lượng" : "Token"}
          </button>
        ))}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto">
        {assistants.length === 0 ? (
          <p className="text-sm text-ink-soft">
            Chưa có câu trả lời nào được lưu (hội thoại lỗi/bị chặn giữa chừng).
          </p>
        ) : (
          assistants.map((m, i) => (
            <div key={m.id} className="space-y-1.5">
              <p className="flex items-center gap-2 text-xs font-semibold text-ink">
                Lượt {i + 1}
                <ConfidenceBadge confidence={m.confidence} />
              </p>
              {tab === "quality" ? (
                <QualityFlags m={m} />
              ) : tokensByMessage.has(m.id) ? (
                <TokenBreakdown tokens={tokensByMessage.get(m.id) as MessageTokens} />
              ) : (
                <p className="text-xs text-ink-faint">Không có dữ liệu token.</p>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
}
