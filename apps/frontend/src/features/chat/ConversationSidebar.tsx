import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Check, MessageSquare, Pencil, Plus, Trash2, X } from "lucide-react";
import type { Conversation } from "@/types";

const ACTION_BTN =
  "rounded-md p-1.5 text-ink-faint transition-colors hover:bg-paper-card hover:text-ink";

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
        <button onClick={onNew} className="btn btn-primary w-full">
          <Plus size={16} />
          Cuộc trò chuyện mới
        </button>
      </div>

      <p className="section-title px-5 pb-2 pt-2">Gần đây</p>

      <div className="flex-1 overflow-y-auto px-3 pb-3">
        {loading ? (
          <p className="px-2 py-2 text-sm text-ink-soft">Đang tải…</p>
        ) : conversations.length === 0 ? (
          <p className="px-2 py-2 text-sm text-ink-soft">Chưa có cuộc trò chuyện nào.</p>
        ) : (
          <ul className="space-y-0.5">
            {conversations.map((c) => {
              const active = c.id === activeId;
              if (editingId === c.id) {
                return (
                  <li key={c.id}>
                    <div className="flex items-center gap-1 rounded-lg bg-paper-sunken p-1">
                      <input
                        ref={inputRef}
                        value={draft}
                        onChange={(e) => setDraft(e.target.value)}
                        onKeyDown={(e) => onEditKeyDown(e, c.id, c.title)}
                        onBlur={() => commitEdit(c.id, c.title)}
                        maxLength={200}
                        className="input h-8 min-w-0 flex-1 px-2 py-1"
                      />
                      <button
                        // onMouseDown: chạy TRƯỚC blur của input để không bị hủy trước khi lưu.
                        onMouseDown={(e) => {
                          e.preventDefault();
                          commitEdit(c.id, c.title);
                        }}
                        aria-label="Lưu tên"
                        className={ACTION_BTN}
                      >
                        <Check size={15} />
                      </button>
                      <button
                        onMouseDown={(e) => {
                          e.preventDefault();
                          cancelEdit();
                        }}
                        aria-label="Hủy"
                        className={ACTION_BTN}
                      >
                        <X size={15} />
                      </button>
                    </div>
                  </li>
                );
              }
              return (
                <li key={c.id} className="group relative">
                  <button
                    onClick={() => onSelect(c.id)}
                    className={`item-row flex items-center gap-2.5 py-2 text-sm group-focus-within:pr-16 group-hover:pr-16 ${
                      active ? "item-row-active font-medium text-brand-dark" : "text-ink"
                    }`}
                    title={c.title}
                  >
                    <MessageSquare
                      size={15}
                      className={`shrink-0 ${active ? "text-brand" : "text-ink-faint"}`}
                    />
                    <span className="truncate">{c.title}</span>
                  </button>
                  <div className="absolute right-1.5 top-1/2 flex -translate-y-1/2 items-center opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
                    <button
                      onClick={() => startEdit(c)}
                      aria-label="Đổi tên"
                      title="Đổi tên"
                      className={ACTION_BTN}
                    >
                      <Pencil size={14} />
                    </button>
                    <button
                      onClick={() => confirmDelete(c)}
                      aria-label="Xóa"
                      title="Xóa"
                      className={`${ACTION_BTN} hover:text-rose-600`}
                    >
                      <Trash2 size={14} />
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
