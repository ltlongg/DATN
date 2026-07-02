import { formatDateTime } from "@/lib/format";
import type { ConversationLogItem } from "@/types/admin";

export function ConversationLogTable({
  items,
  onOpen,
}: {
  items: ConversationLogItem[];
  onOpen: (id: string) => void;
}) {
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-paper-border text-left text-ink-soft">
          <th className="py-2 pr-4 font-medium">Người dùng</th>
          <th className="py-2 pr-4 font-medium">Tiêu đề</th>
          <th className="py-2 pr-4 font-medium">Số message</th>
          <th className="py-2 pr-4 font-medium">Cập nhật</th>
          <th className="py-2 font-medium"></th>
        </tr>
      </thead>
      <tbody>
        {items.map((c) => (
          <tr key={c.id} className="border-b border-paper-border">
            <td className="py-2 pr-4 text-ink">
              {c.user_name}
              <span className="block text-xs text-ink-soft">{c.user_email}</span>
            </td>
            <td className="py-2 pr-4 text-ink">{c.title}</td>
            <td className="py-2 pr-4 text-ink-soft">{c.message_count}</td>
            <td className="py-2 pr-4 text-ink-soft">{formatDateTime(c.updated_at)}</td>
            <td className="py-2 text-right">
              <button onClick={() => onOpen(c.id)} className="text-brand hover:underline">
                Xem
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
