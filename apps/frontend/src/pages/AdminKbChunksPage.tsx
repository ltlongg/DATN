import { PageHeader } from "@/components/PageHeader";
import { ChunksTab } from "@/features/kb/ChunksTab";

export default function AdminKbChunksPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Đoạn tài liệu"
        desc="Tra cứu chunk đã index: nội dung, metadata, thực thể & sự kiện tham chiếu."
      />
      <ChunksTab />
    </div>
  );
}
