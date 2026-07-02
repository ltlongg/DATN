import { useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { ConfigTabStub } from "@/features/advanced/ConfigTabStub";
import { CostTab } from "@/features/advanced/CostTab";
import { LogsTab } from "@/features/advanced/LogsTab";
import { UsersTab } from "@/features/advanced/UsersTab";

type TabKey = "logs" | "users" | "cost" | "config";

/** Module 4 — Admin nâng cao. 3 tab build thật + tab Cấu hình (stub "Sắp cập nhật"). */
export default function AdminAdvancedPage() {
  const [tab, setTab] = useState<TabKey>("logs");

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-semibold text-ink">Quản trị nâng cao</h2>

      <Tabs.Root value={tab} onValueChange={(v) => setTab(v as TabKey)}>
        <Tabs.List className="flex flex-wrap gap-1 border-b border-paper-border">
          <TabTrigger value="logs" label="Hội thoại & chất lượng" />
          <TabTrigger value="users" label="Người dùng & quota" />
          <TabTrigger value="cost" label="Chi phí" />
          <TabTrigger value="config" label="Cấu hình hệ thống" />
        </Tabs.List>

        <div className="pt-4">
          <Tabs.Content value="logs">
            <LogsTab />
          </Tabs.Content>
          <Tabs.Content value="users">
            <UsersTab />
          </Tabs.Content>
          <Tabs.Content value="cost">
            <CostTab />
          </Tabs.Content>
          <Tabs.Content value="config">
            <ConfigTabStub />
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
