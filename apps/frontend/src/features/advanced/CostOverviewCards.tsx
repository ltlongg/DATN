import { StatCard } from "@/components/StatCard";
import type { CostOverview } from "@/types/admin";

const nf = new Intl.NumberFormat("vi-VN");

export function CostOverviewCards({ overview }: { overview: CostOverview }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <StatCard label="Lượt gọi LLM" value={nf.format(overview.total_calls)} />
      <StatCard label="Tổng token" value={nf.format(overview.total_tokens)} />
      <StatCard label="TB token/lượt" value={nf.format(overview.avg_tokens_per_call)} />
      <StatCard label="Token prompt" value={nf.format(overview.total_prompt_tokens)} />
      <StatCard label="Token completion" value={nf.format(overview.total_completion_tokens)} />
    </div>
  );
}
