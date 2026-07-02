import { useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { ChunksTab } from "@/features/kb/ChunksTab";
import { GraphTab } from "@/features/kb/GraphTab";
import { TimelineTab } from "@/features/kb/TimelineTab";

type TabKey = "chunks" | "graph" | "timeline";

/**
 * KB Inspector (read-only). 3 tab + điều hướng chéo bằng chunk_id — khóa nối duy nhất giữa
 * Postgres (chunk/event) và Neo4j (entity). Chọn item ở tab này -> mở tab liên quan.
 */
export default function AdminKbPage() {
  const [tab, setTab] = useState<TabKey>("chunks");
  const [chunkId, setChunkId] = useState<string | null>(null);
  const [entityNorm, setEntityNorm] = useState<string | null>(null);
  const [eventId, setEventId] = useState<string | null>(null);

  function navChunk(id: string) {
    setChunkId(id);
    setTab("chunks");
  }
  function navEntity(norm: string) {
    setEntityNorm(norm);
    setTab("graph");
  }
  function navEvent(id: string) {
    setEventId(id);
    setTab("timeline");
  }

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-ink">Trình xem kho tri thức</h2>

      <Tabs.Root value={tab} onValueChange={(v) => setTab(v as TabKey)}>
        <Tabs.List className="flex gap-1 border-b border-paper-border">
          <TabTrigger value="chunks" label="Chunks" />
          <TabTrigger value="graph" label="Đồ thị tri thức" />
          <TabTrigger value="timeline" label="Dòng thời gian" />
        </Tabs.List>

        <div className="pt-4">
          <Tabs.Content value="chunks">
            <ChunksTab
              selectedChunkId={chunkId}
              onSelectChunk={setChunkId}
              onNavEntity={navEntity}
              onNavEvent={navEvent}
            />
          </Tabs.Content>
          <Tabs.Content value="graph">
            <GraphTab
              selectedNorm={entityNorm}
              onSelectEntity={setEntityNorm}
              onNavChunk={navChunk}
            />
          </Tabs.Content>
          <Tabs.Content value="timeline">
            <TimelineTab
              selectedEventId={eventId}
              onSelectEvent={setEventId}
              onNavChunk={navChunk}
            />
          </Tabs.Content>
        </div>
      </Tabs.Root>
    </div>
  );
}

function TabTrigger({ value, label }: { value: string; label: string }) {
  return (
    <Tabs.Trigger
      value={value}
      className="border-b-2 border-transparent px-4 py-2 text-sm text-ink-soft data-[state=active]:border-brand data-[state=active]:text-brand"
    >
      {label}
    </Tabs.Trigger>
  );
}
