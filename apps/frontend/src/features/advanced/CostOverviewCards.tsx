import type { CostOverview } from "@/types/admin";

function Card({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-paper-border bg-paper-card p-3">
      <p className="text-xs text-ink-soft">{label}</p>
      <p className="mt-1 text-xl font-semibold text-ink">{value}</p>
    </div>
  );
}

const nf = new Intl.NumberFormat("vi-VN");

export function CostOverviewCards({ overview }: { overview: CostOverview }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <Card label="Lượt gọi LLM" value={nf.format(overview.total_calls)} />
      <Card label="Tổng token" value={nf.format(overview.total_tokens)} />
      <Card label="TB token/lượt" value={nf.format(overview.avg_tokens_per_call)} />
      <Card label="Token prompt" value={nf.format(overview.total_prompt_tokens)} />
      <Card label="Token completion" value={nf.format(overview.total_completion_tokens)} />
    </div>
  );
}
