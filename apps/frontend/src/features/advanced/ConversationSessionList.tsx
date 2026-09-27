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
    <ul className="space-y-1">
      {items.map((c) => {
        const active = c.id === selectedId;
        const tok = tokensByConv.get(c.id);
        return (
          <li key={c.id}>
            <button
              onClick={() => onSelect(c.id)}
              className={`w-full rounded-md border px-2.5 py-2 text-left transition-colors ${
                active
                  ? "border-brand bg-brand/10"
                  : "border-transparent hover:border-paper-border hover:bg-paper"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                {/* Tên chỉ có khi hội thoại có tin vi phạm; còn lại hiện mã ẩn danh. */}
                <span className="truncate text-sm font-medium text-ink">
                  {c.user_name ?? c.user_anon_id}
                </span>
                <span className="shrink-0 text-[11px] text-ink-soft">
                  {formatDateTime(c.updated_at)}
                </span>
              </div>
              <p className="mt-0.5 truncate text-xs text-ink-soft">
                {c.title ?? <span className="italic">Tiêu đề được ẩn</span>}
              </p>
              <p className="mt-0.5 text-[11px] text-ink-soft">
                {c.message_count} lượt · {tok === undefined ? "—" : `${nf.format(tok)} token`}
              </p>
              {(c.shared || c.flagged_count > 0) && (
                <div className="mt-1 flex flex-wrap gap-1">
                  {c.shared && (
                    <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[11px] text-emerald-800">
                      Đã chia sẻ
                    </span>
                  )}
                  {c.flagged_count > 0 && (
                    <span className="rounded-full bg-rose-100 px-2 py-0.5 text-[11px] text-rose-800">
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
