import { PageHeader } from "@/components/PageHeader";
import { ConfigForm } from "@/features/advanced/ConfigForm";

export default function AdminConfigPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Cấu hình hệ thống"
        desc="Tinh chỉnh retrieval + synthesize, áp dụng LIVE cho agent-service (hiệu lực tối đa 60 giây)."
      />
      <ConfigForm />
    </div>
  );
}
