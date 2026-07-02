import type { Conversation } from "@/types";

/** Sidebar danh sách phiên + nút tạo mới. Phiên đang chọn được highlight. */
export function ConversationSidebar({
  conversations,
  activeId,
  loading,
  onSelect,
  onNew,
}: {
  conversations: Conversation[];
  activeId: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
}) {
  return (
    <aside className="flex w-64 shrink-0 flex-col border-r border-paper-border bg-paper-card">
      <div className="p-3">
        <button
          onClick={onNew}
          className="w-full rounded-lg border border-brand bg-brand px-3 py-2 text-sm font-medium text-brand-fg hover:bg-brand-dark"
        >
          + Cuộc trò chuyện mới
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 pb-3">
        {loading ? (
          <p className="px-2 py-2 text-sm text-ink-soft">Đang tải…</p>
        ) : conversations.length === 0 ? (
          <p className="px-2 py-2 text-sm text-ink-soft">Chưa có cuộc trò chuyện nào.</p>
        ) : (
          <ul className="space-y-1">
            {conversations.map((c) => (
              <li key={c.id}>
                <button
                  onClick={() => onSelect(c.id)}
                  className={`w-full truncate rounded-md px-3 py-2 text-left text-sm ${
                    c.id === activeId
                      ? "bg-brand/10 font-medium text-brand"
                      : "text-ink hover:bg-paper"
                  }`}
                  title={c.title}
                >
                  {c.title}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
