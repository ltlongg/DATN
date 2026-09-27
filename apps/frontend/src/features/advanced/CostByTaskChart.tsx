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
import type { TaskCost } from "@/types/admin";

const LABELS: Record<string, string> = {
  plan: "Phân tích câu hỏi",
  // Node `plan` từng tên là `build_query`; log cũ vẫn mang task đó nên phải có nhãn riêng,
  // nếu gộp một nhãn thì hai giai đoạn trông như một và không ai biết mốc đổi ở đâu.
  build_query: "Phân tích câu hỏi (cũ)",
  resolve: "Trích mắt xích",
  synthesize: "Soạn câu trả lời",
};

/** So sánh token giữa các task LLM online (chỉ total_tokens theo task). */
export function CostByTaskChart({ data }: { data: TaskCost[] }) {
  const rows = data.map((d) => ({ ...d, label: LABELS[d.task] ?? d.task }));
  return (
    <div>
      <p className="mb-3 text-sm font-semibold text-ink">Token theo tác vụ</p>
      {rows.length === 0 ? (
        <EmptyState>Chưa có dữ liệu theo tác vụ.</EmptyState>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
            <CartesianGrid vertical={false} stroke={palette.paper.border} />
            <XAxis dataKey="label" {...CHART_AXIS} />
            <YAxis {...CHART_Y_AXIS} />
            <Tooltip {...CHART_TOOLTIP} />
            <Bar
              dataKey="total_tokens"
              name="Token"
              fill={palette.gold.DEFAULT}
              radius={[4, 4, 0, 0]}
              maxBarSize={56}
            />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
