import { StatCard } from "@/components/StatCard";
import type { QualitySummary } from "@/types/admin";

function pct(num: number, den: number): string {
  if (den === 0) return "—";
  return `${Math.round((num / den) * 100)}%`;
}

/**
 * Tổng hợp chất lượng. no_citation lấy MẪU SỐ = retrieval_attempted_count (KHÔNG phải
 * total_assistant_messages) — message route clarify/smalltalk/out_of_scope vốn không có
 * citation, chia nhầm mẫu số làm tỷ lệ thấp giả (xem backend-additions §3.1).
 */
export function QualitySummaryCard({ summary }: { summary: QualitySummary }) {
  const t = summary.total_assistant_messages;
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <StatCard label="Message trả lời" value={String(t)} sub="tổng cộng" />
      <StatCard
        label="Thiếu citation"
        value={`${summary.no_citation_count} / ${summary.retrieval_attempted_count}`}
        sub={`${pct(summary.no_citation_count, summary.retrieval_attempted_count)} lượt có truy hồi`}
      />
      <StatCard
        label="Độ tin cậy thấp"
        value={String(summary.low_confidence_count)}
        sub={`${pct(summary.low_confidence_count, t)} tổng`}
      />
      <StatCard
        label="Cần làm rõ"
        value={String(summary.clarification_count)}
        sub={`${pct(summary.clarification_count, t)} tổng`}
      />
      <StatCard
        label="Có cảnh báo"
        value={String(summary.warning_count)}
        sub={`${pct(summary.warning_count, t)} tổng`}
      />
    </div>
  );
}
