import { EmptyState } from "@/components/EmptyState";
import type { TopUserCost } from "@/types/admin";

const nf = new Intl.NumberFormat("vi-VN");

export function TopUsersTable({ users }: { users: TopUserCost[] }) {
  return (
    <div className="card overflow-hidden">
      <p className="border-b border-paper-border px-5 py-3.5 text-sm font-semibold text-ink">
        Người dùng tốn token nhất
      </p>
      {users.length === 0 ? (
        <div className="p-4">
          <EmptyState>Chưa có dữ liệu.</EmptyState>
        </div>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Người dùng</th>
              <th className="text-right">Số lượt</th>
              <th className="text-right">Tổng token</th>
            </tr>
          </thead>
          <tbody>
            {users.map((u) => (
              <tr key={u.user_id}>
                <td>
                  <p className="font-medium">{u.name}</p>
                  <p className="text-xs text-ink-soft">{u.email}</p>
                </td>
                <td className="text-right tabular-nums text-ink-soft">{u.call_count}</td>
                <td className="text-right font-medium tabular-nums">{nf.format(u.total_tokens)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
