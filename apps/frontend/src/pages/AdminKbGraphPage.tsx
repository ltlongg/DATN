import { PageHeader } from "@/components/PageHeader";
import { GraphTab } from "@/features/kb/GraphTab";

export default function AdminKbGraphPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Đồ thị tri thức"
        desc="Duyệt thực thể và quan hệ 1-hop trích từ tài liệu (ego-graph)."
      />
      <GraphTab />
    </div>
  );
}
