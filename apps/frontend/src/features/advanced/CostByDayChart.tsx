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
import type { DailyCost } from "@/types/admin";

/** Token theo ngày. DailyCost chỉ có total_tokens (không tách prompt/completion theo ngày). */
export function CostByDayChart({ data }: { data: DailyCost[] }) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-ink">Token theo ngày</p>
      {data.length === 0 ? (
        <EmptyState>Chưa có dữ liệu theo ngày.</EmptyState>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e7ddcc" />
            <XAxis dataKey="day" fontSize={11} />
            <YAxis fontSize={11} />
            <Tooltip />
            <Bar dataKey="total_tokens" name="Token" fill="#A4161A" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
