import { Pencil } from "lucide-react";
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
    <div className="card overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>Người dùng</th>
            <th>Vai trò</th>
            <th>Trạng thái</th>
            <th className="text-right">Quota/ngày</th>
            <th className="text-right">Tin bị gắn cờ</th>
            <th>Ngày tạo</th>
            <th>
              <span className="sr-only">Thao tác</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id}>
              <td>
                <div className="flex items-center gap-3">
                  <span
                    aria-hidden
                    className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-paper-sunken text-xs font-semibold text-ink-soft"
                  >
                    {u.name.trim().charAt(0).toUpperCase() || "?"}
                  </span>
                  <div className="min-w-0">
                    <p className="font-medium">{u.name}</p>
                    <p className="text-xs text-ink-soft">{u.email}</p>
                  </div>
                </div>
              </td>
              <td className="align-middle">
                <span className={`badge ${u.role === "admin" ? "badge-brand" : "badge-neutral"}`}>
                  {u.role}
                </span>
              </td>
              <td className="align-middle">
                <span className={`badge ${u.is_active ? "badge-success" : "badge-danger"}`}>
                  {u.is_active ? "Hoạt động" : "Đã khóa"}
                </span>
              </td>
              <td className="text-right align-middle tabular-nums text-ink-soft">
                {u.question_quota == null ? "không giới hạn" : u.question_quota}
              </td>
              <td
                className={`text-right align-middle tabular-nums ${
                  u.flagged_count > 0 ? "font-semibold text-rose-700" : "text-ink-soft"
                }`}
              >
                {u.flagged_count}
              </td>
              <td className="whitespace-nowrap align-middle text-ink-soft">
                {formatDateTime(u.created_at)}
              </td>
              <td className="py-2 text-right align-middle">
                <button onClick={() => onEdit(u)} className="btn btn-sm btn-ghost">
                  <Pencil size={14} />
                  Sửa
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
