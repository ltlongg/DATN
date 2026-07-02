import { StatusBadge } from "@/features/admin/StatusBadge";
import { formatDateTime } from "@/lib/format";
import type { Document } from "@/types";

/** Bảng tài liệu (presentational). Hành động sửa/xoá do trang cha xử lý. */
export function DocumentTable({
  documents,
  onEdit,
  onDelete,
}: {
  documents: Document[];
  onEdit: (doc: Document) => void;
  onDelete: (doc: Document) => void;
}) {
  return (
    <table className="w-full border-collapse text-sm">
      <thead>
        <tr className="border-b border-paper-border text-left text-ink-soft">
          <th className="py-2 pr-4 font-medium">Tên</th>
          <th className="py-2 pr-4 font-medium">Loại</th>
          <th className="py-2 pr-4 font-medium">Trạng thái</th>
          <th className="py-2 pr-4 font-medium">Số chunk</th>
          <th className="py-2 pr-4 font-medium">Ngày tạo</th>
          <th className="py-2 font-medium"></th>
        </tr>
      </thead>
      <tbody>
        {documents.map((doc) => (
          <tr key={doc.id} className="border-b border-paper-border">
            <td className="py-2 pr-4 text-ink">{doc.name}</td>
            <td className="py-2 pr-4 text-ink-soft">{doc.type}</td>
            <td className="py-2 pr-4">
              <StatusBadge status={doc.status} />
            </td>
            <td className="py-2 pr-4 text-ink-soft">{doc.chunk_count}</td>
            <td className="py-2 pr-4 text-ink-soft">{formatDateTime(doc.created_at)}</td>
            <td className="py-2 text-right">
              <button
                onClick={() => onEdit(doc)}
                className="mr-3 text-ink-soft hover:text-brand"
              >
                Sửa
              </button>
              <button onClick={() => onDelete(doc)} className="text-ink-soft hover:text-rose-700">
                Xoá
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
