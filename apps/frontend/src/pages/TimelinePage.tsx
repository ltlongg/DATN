import { PageHeader } from "@/components/PageHeader";
import { TimelineSpine } from "@/features/explore/TimelineSpine";

export default function TimelinePage() {
  return (
    <div className="flex h-full flex-col">
      <div className="shrink-0 border-b border-paper-border px-6 py-4">
        <PageHeader
          title="Dòng lịch sử"
          desc="Toàn bộ sự kiện lịch sử xếp theo dòng chảy thời gian."
        />
      </div>
      <div className="min-h-0 flex-1">
        <TimelineSpine />
      </div>
    </div>
  );
}
