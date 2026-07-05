import { PageHeader } from "@/components/PageHeader";
import { CostTab } from "@/features/advanced/CostTab";

export default function AdminCostPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Chi phí"
        desc="Thống kê token LLM online: theo ngày, theo tác vụ và top người dùng."
      />
      <CostTab />
    </div>
  );
}
