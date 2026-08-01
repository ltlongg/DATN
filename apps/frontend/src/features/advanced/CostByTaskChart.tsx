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
      <p className="mb-2 text-sm font-medium text-ink">Token theo tác vụ</p>
      {rows.length === 0 ? (
        <EmptyState>Chưa có dữ liệu theo tác vụ.</EmptyState>
      ) : (
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={rows} margin={{ top: 8, right: 8, bottom: 8, left: 8 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e7ddcc" />
            <XAxis dataKey="label" fontSize={11} />
            <YAxis fontSize={11} />
            <Tooltip />
            <Bar dataKey="total_tokens" name="Token" fill="#c4494c" radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
