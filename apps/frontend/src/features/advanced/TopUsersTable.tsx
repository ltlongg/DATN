import { EmptyState } from "@/components/EmptyState";
import type { TopUserCost } from "@/types/admin";

const nf = new Intl.NumberFormat("vi-VN");

export function TopUsersTable({ users }: { users: TopUserCost[] }) {
  return (
    <div>
      <p className="mb-2 text-sm font-medium text-ink">Người dùng tốn token nhất</p>
      {users.length === 0 ? (
        <EmptyState>Chưa có dữ liệu.</EmptyState>
      ) : (
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-paper-border text-left text-ink-soft">
              <th className="py-2 pr-4 font-medium">Người dùng</th>
              <th className="py-2 pr-4 font-medium">Số lượt</th>
              <th className="py-2 font-medium">Tổng token</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.user_id} className="border-b border-paper-border">
                <td className="py-2 pr-4 text-ink">
                  {u.name}
                  <span className="block text-xs text-ink-soft">{u.email}</span>
                </td>
                <td className="py-2 pr-4 text-ink-soft">{u.call_count}</td>
                <td className="py-2 text-ink">{nf.format(u.total_tokens)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
