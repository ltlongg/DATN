import { PageHeader } from "@/components/PageHeader";
import { ConfigTabStub } from "@/features/advanced/ConfigTabStub";

export default function AdminConfigPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Cấu hình hệ thống"
        desc="Chế độ truy hồi mặc định và tinh chỉnh retrieval/synthesize."
      />
      <ConfigTabStub />
    </div>
  );
}
