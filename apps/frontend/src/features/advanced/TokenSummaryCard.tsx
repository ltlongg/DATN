import { StatCard } from "@/components/StatCard";
import type { TokenOverall } from "@/types/admin";

const nf = new Intl.NumberFormat("vi-VN");

/**
 * Token của các lượt gọi LLM ĐÃ gắn hội thoại trong khoảng ngày (song song QualitySummaryCard,
 * không thay thế). Tổng honest toàn hệ thống (kể cả usage cũ chưa gắn hội thoại) xem tab Chi phí.
 */
export function TokenSummaryCard({ overall }: { overall: TokenOverall }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <StatCard label="Lượt gọi LLM" value={nf.format(overall.total_calls)} sub="đã gắn hội thoại" />
      <StatCard label="Token vào" value={nf.format(overall.total_prompt_tokens)} />
      <StatCard label="Token ra" value={nf.format(overall.total_completion_tokens)} />
      <StatCard label="Tổng token" value={nf.format(overall.total_tokens)} />
      <StatCard label="TB token/lượt" value={nf.format(overall.avg_tokens_per_call)} />
    </div>
  );
}
