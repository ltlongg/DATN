import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getCostByDay, getCostByTask, getCostOverview, getTopUsers } from "@/api/cost";
import { Alert } from "@/components/Alert";
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
        <Alert>Không tải được số liệu chi phí.</Alert>
      ) : overview.data ? (
        <>
          {overview.data.total_calls === 0 && (
            <p className="rounded-xl border border-dashed border-paper-border px-4 py-3 text-sm text-ink-soft">
              Chưa có dữ liệu chi phí — hỏi thử vài câu ở khu chat để xem thống kê.
            </p>
          )}
          <CostOverviewCards overview={overview.data} />
          <CostEstimateInput totalTokens={overview.data.total_tokens} />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="card p-5">
              <CostByDayChart data={byDay.data ?? []} />
            </div>
            <div className="card p-5">
              <CostByTaskChart data={byTask.data ?? []} />
            </div>
          </div>
          <TopUsersTable users={topUsers.data ?? []} />
        </>
      ) : null}
    </div>
  );
}
