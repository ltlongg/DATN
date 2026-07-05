import { PageHeader } from "@/components/PageHeader";
import { LogsTab } from "@/features/advanced/LogsTab";

export default function AdminLogsPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Hội thoại & chất lượng"
        desc="Log hội thoại và các chỉ số chất lượng câu trả lời."
      />
      <LogsTab />
    </div>
  );
}
