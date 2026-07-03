import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Check, Pencil, Trash2, X } from "lucide-react";
import type { Conversation } from "@/types";

/** Sidebar danh sách phiên + nút tạo mới. Phiên đang chọn được highlight.
 * Mỗi phiên có thể đổi tên (inline) hoặc xóa (xác nhận trước). */
export function ConversationSidebar({
  conversations,
  activeId,
  loading,
  onSelect,
  onNew,
  onRename,
  onDelete,
}: {
  conversations: Conversation[];
  activeId: string | null;
  loading: boolean;
  onSelect: (id: string) => void;
  onNew: () => void;
  onRename: (id: string, title: string) => void;
  onDelete: (id: string) => void;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editingId) inputRef.current?.select();
  }, [editingId]);

  function startEdit(c: Conversation) {
    setEditingId(c.id);
    setDraft(c.title);
  }

  function cancelEdit() {
    setEditingId(null);
    setDraft("");
  }

  function commitEdit(id: string, original: string) {
    const next = draft.trim();
    if (next && next !== original) onRename(id, next);
    cancelEdit();
  }

  function onEditKeyDown(e: KeyboardEvent<HTMLInputElement>, id: string, original: string) {
    if (e.key === "Enter") {
      e.preventDefault();
      commitEdit(id, original);
    } else if (e.key === "Escape") {
      e.preventDefault();
      cancelEdit();
    }
  }

  function confirmDelete(c: Conversation) {
    if (window.confirm(`Xóa cuộc trò chuyện "${c.title}"? Hành động này không thể hoàn tác.`)) {
      onDelete(c.id);
    }
  }

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
            {conversations.map((c) => {
              const active = c.id === activeId;
              if (editingId === c.id) {
                return (
                  <li key={c.id}>
                    <div className="flex items-center gap-1 rounded-md bg-brand/10 px-2 py-1">
                      <input
                        ref={inputRef}
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={(e) => onEditKeyDown(e, c.id, c.title)}
                        onBlur={() => commitEdit(c.id, c.title)}
                        maxLength={200}
                        className="min-w-0 flex-1 rounded border border-paper-border bg-white px-2 py-1 text-sm text-ink outline-none focus:border-brand"
                      />
                      <button
                        // onMouseDown: chạy TRƯỚC blur của input để không bị hủy trước khi lưu.
                        onMouseDown={(e) => {
                          e.preventDefault();
                          commitEdit(c.id, c.title);
                        }}
                        aria-label="Lưu tên"
                        className="rounded p-1 text-ink-soft hover:bg-paper hover:text-brand"
                      >
                        <Check size={16} />
                      </button>
                      <button
                        onMouseDown={(e) => {
                          e.preventDefault();
                          cancelEdit();
                        }}
                        aria-label="Hủy"
                        className="rounded p-1 text-ink-soft hover:bg-paper hover:text-brand"
                      >
                        <X size={16} />
                      </button>
                    </div>
                  </li>
                );
              }
              return (
                <li key={c.id} className="group relative">
                  <button
                    onClick={() => onSelect(c.id)}
                    className={`w-full truncate rounded-md py-2 pl-3 pr-14 text-left text-sm ${
                      active
                        ? "bg-brand/10 font-medium text-brand"
                        : "text-ink hover:bg-paper"
                    }`}
                    title={c.title}
                  >
                    {c.title}
                  </button>
                  <div className="absolute right-1 top-1/2 flex -translate-y-1/2 items-center gap-0.5 opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
                    <button
                      onClick={() => startEdit(c)}
                      aria-label="Đổi tên"
                      title="Đổi tên"
                      className="rounded p-1 text-ink-soft hover:bg-paper hover:text-brand"
                    >
                      <Pencil size={15} />
                    </button>
                    <button
                      onClick={() => confirmDelete(c)}
                      aria-label="Xóa"
                      title="Xóa"
                      className="rounded p-1 text-ink-soft hover:bg-paper hover:text-brand"
                    >
                      <Trash2 size={15} />
                    </button>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </aside>
  );
}
