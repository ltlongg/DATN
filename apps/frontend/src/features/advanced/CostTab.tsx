import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getCostByDay, getCostByTask, getCostOverview, getTopUsers } from "@/api/cost";
import { Spinner } from "@/components/Spinner";
import { CostByDayChart } from "@/features/advanced/CostByDayChart";
import { CostByTaskChart } from "@/features/advanced/CostByTaskChart";
import { CostEstimateInput } from "@/features/advanced/CostEstimateInput";
import { CostFilterBar, defaultRange, type CostRangeValue } from "@/features/advanced/CostFilterBar";
import { CostOverviewCards } from "@/features/advanced/CostOverviewCards";
import { TopUsersTable } from "@/features/advanced/TopUsersTable";

export function CostTab() {
  const [range, setRange] = useState<CostRangeValue>(defaultRange);

  const overview = useQuery({
    queryKey: ["cost-overview", range],
    queryFn: () => getCostOverview(range),
  });
  const byDay = useQuery({ queryKey: ["cost-day", range], queryFn: () => getCostByDay(range) });
  const byTask = useQuery({ queryKey: ["cost-task", range], queryFn: () => getCostByTask(range) });
  const topUsers = useQuery({
    queryKey: ["cost-top", range],
    queryFn: () => getTopUsers({ ...range, limit: 10 }),
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <CostFilterBar initial={range} onApply={setRange} />
      </div>

      {overview.isLoading ? (
        <Spinner />
      ) : overview.isError ? (
        <p className="text-sm text-rose-700">Không tải được số liệu chi phí.</p>
      ) : overview.data ? (
        <>
          {overview.data.total_calls === 0 && (
            <p className="rounded-md bg-paper p-3 text-sm text-ink-soft">
              Chưa có dữ liệu chi phí — hỏi thử vài câu ở khu chat để xem thống kê.
            </p>
          )}
          <CostOverviewCards overview={overview.data} />
          <CostEstimateInput totalTokens={overview.data.total_tokens} />
          <div className="grid grid-cols-1 gap-6 rounded-lg border border-paper-border bg-paper-card p-4 lg:grid-cols-2">
            <CostByDayChart data={byDay.data ?? []} />
            <CostByTaskChart data={byTask.data ?? []} />
          </div>
          <div className="rounded-lg border border-paper-border bg-paper-card p-4">
            <TopUsersTable users={topUsers.data ?? []} />
          </div>
        </>
      ) : null}
    </div>
  );
}
