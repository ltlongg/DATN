import { formatDateTime } from "@/lib/format";
import type { ConversationLogItem } from "@/types/admin";

const nf = new Intl.NumberFormat("vi-VN");

/** Cột trái: danh sách phiên hội thoại, chọn 1 để replay ở cột giữa. */
export function ConversationSessionList({
  items,
  selectedId,
  tokensByConv,
  onSelect,
}: {
  items: ConversationLogItem[];
  selectedId: string | null;
  tokensByConv: Map<string, number>;
  onSelect: (id: string) => void;
}) {
  return (
    <ul className="space-y-0.5">
      {items.map((c) => {
        const active = c.id === selectedId;
        const tok = tokensByConv.get(c.id);
        return (
          <li key={c.id}>
            <button
              onClick={() => onSelect(c.id)}
              className={`item-row ${active ? "item-row-active" : ""}`}
            >
              <div className="flex items-center justify-between gap-2">
                {/* Tên chỉ có khi hội thoại có tin vi phạm; còn lại hiện mã ẩn danh. */}
                <span className="truncate text-sm font-medium text-ink">
                  {c.user_name ?? c.user_anon_id}
                </span>
                <span className="shrink-0 text-[11px] tabular-nums text-ink-faint">
                  {formatDateTime(c.updated_at)}
                </span>
              </div>
              <p className="mt-0.5 truncate text-xs text-ink-soft">
                {c.title ?? <span className="italic">Tiêu đề được ẩn</span>}
              </p>
              <p className="mt-0.5 text-[11px] text-ink-faint">
                {c.message_count} lượt · {tok === undefined ? "—" : `${nf.format(tok)} token`}
              </p>
              {(c.shared || c.flagged_count > 0) && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {c.shared && <span className="badge badge-success">Đã chia sẻ</span>}
                  {c.flagged_count > 0 && (
                    <span className="badge badge-danger">
                      {c.flagged_count} tin bị gắn cờ
                    </span>
                  )}
                </div>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
