import { PageHeader } from "@/components/PageHeader";
import { TimelineTab } from "@/features/kb/TimelineTab";

export default function AdminKbTimelinePage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Dòng thời gian"
        desc="Các sự kiện atomic (when–where–what) trích cho timeline & bản đồ."
      />
      <TimelineTab />
    </div>
  );
}
