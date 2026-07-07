import { PageHeader } from "@/components/PageHeader";
import { ActivityTab } from "@/features/advanced/ActivityTab";

export default function AdminActivityPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Hoạt động hệ thống"
        desc="Nhật ký mỗi request tới API: phần nào OK hay lỗi, mất bao lâu, lỗi gì."
      />
      <ActivityTab />
    </div>
  );
}
