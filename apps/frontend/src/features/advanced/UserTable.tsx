import { formatDateTime } from "@/lib/format";
import type { UserOut } from "@/types/admin";

export function UserTable({
  users,
  onEdit,
}: {
  users: UserOut[];
  onEdit: (user: UserOut) => void;
}) {
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-paper-border text-left text-ink-soft">
          <th className="py-2 pr-4 font-medium">Email</th>
          <th className="py-2 pr-4 font-medium">Tên</th>
          <th className="py-2 pr-4 font-medium">Vai trò</th>
          <th className="py-2 pr-4 font-medium">Trạng thái</th>
          <th className="py-2 pr-4 font-medium">Quota/ngày</th>
          <th className="py-2 pr-4 font-medium">Ngày tạo</th>
          <th className="py-2 font-medium"></th>
        </tr>
      </thead>
      <tbody>
        {users.map((u) => (
          <tr key={u.id} className="border-b border-paper-border">
            <td className="py-2 pr-4 text-ink">{u.email}</td>
            <td className="py-2 pr-4 text-ink">{u.name}</td>
            <td className="py-2 pr-4">
              <span className="rounded-full bg-paper px-2 py-0.5 text-xs text-ink-soft">
                {u.role}
              </span>
            </td>
            <td className="py-2 pr-4">
              <span
                className={`rounded-full px-2 py-0.5 text-xs ${
                  u.is_active ? "bg-emerald-100 text-emerald-800" : "bg-rose-100 text-rose-800"
                }`}
              >
                {u.is_active ? "Hoạt động" : "Đã khóa"}
              </span>
            </td>
            <td className="py-2 pr-4 text-ink-soft">
              {u.question_quota == null ? "không giới hạn" : u.question_quota}
            </td>
            <td className="py-2 pr-4 text-ink-soft">{formatDateTime(u.created_at)}</td>
            <td className="py-2 text-right">
              <button onClick={() => onEdit(u)} className="text-brand hover:underline">
                Sửa
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
