import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { EmptyState } from "@/components/EmptyState";
import { CHART_AXIS, CHART_TOOLTIP, CHART_Y_AXIS } from "@/features/advanced/chartStyle";
import { palette } from "@/theme";
import type { DailyCost } from "@/types/admin";

/** Token theo ngày. DailyCost chỉ có total_tokens (không tách prompt/completion theo ngày). */
export function CostByDayChart({ data }: { data: DailyCost[] }) {
  return (
    <div>
      <p className="mb-3 text-sm font-semibold text-ink">Token theo ngày</p>
      {data.length === 0 ? (
        <EmptyState>Chưa có dữ liệu theo ngày.</EmptyState>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.paper.border} />
            <XAxis dataKey="day" {...CHART_AXIS} />
            <YAxis {...CHART_Y_AXIS} />
            <Tooltip {...CHART_TOOLTIP} />
            <Bar
              dataKey="total_tokens"
              name="Token"
              fill={palette.brand.DEFAULT}
              radius={[4, 4, 0, 0]}
              maxBarSize={40}
            />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
