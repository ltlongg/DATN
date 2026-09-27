import { Pencil, Trash2 } from "lucide-react";
import { StatusBadge } from "@/features/admin/StatusBadge";
import { formatDateTime } from "@/lib/format";
import type { Document } from "@/types";

/** Bảng tài liệu (presentational). Hành động sửa/xoá do trang cha xử lý.
 *
 * Số chunk/sự kiện là ĐẾM THẬT từ kho tri thức (backend join `rag_chunks`/`timeline_events`
 * qua `source_file`), không phải số admin nhập. Tài liệu chưa gắn nguồn -> hiện "—".
 */
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
    <div className="card overflow-x-auto">
      <table className="data-table">
        <thead>
          <tr>
            <th>Tên</th>
            <th>Nguồn trong kho</th>
            <th>Loại</th>
            <th>Trạng thái</th>
            <th className="text-right">Số chunk</th>
            <th className="text-right">Sự kiện</th>
            <th>Ngày tạo</th>
            <th>
              <span className="sr-only">Thao tác</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <tr key={doc.id}>
              <td className="font-medium">{doc.name}</td>
              <td>
                {doc.source_file ? (
                  <code className="rounded bg-paper-sunken px-1.5 py-0.5 font-mono text-xs text-ink-soft">
                    {doc.source_file}
                  </code>
                ) : (
                  <span className="text-xs text-ink-faint">Chưa gắn nguồn</span>
                )}
              </td>
              <td className="text-ink-soft">{doc.type}</td>
              <td>
                <StatusBadge status={doc.status} />
              </td>
              <td className="text-right tabular-nums text-ink-soft">
                {doc.source_file ? doc.chunk_count.toLocaleString("vi-VN") : "—"}
              </td>
              <td className="text-right tabular-nums text-ink-soft">
                {doc.source_file ? doc.event_count.toLocaleString("vi-VN") : "—"}
              </td>
              <td className="whitespace-nowrap text-ink-soft">{formatDateTime(doc.created_at)}</td>
              <td className="whitespace-nowrap py-2 text-right">
                <button onClick={() => onEdit(doc)} className="btn btn-sm btn-ghost">
                  <Pencil size={14} />
                  Sửa
                </button>
                {/* Tài liệu còn chunk trong kho: xoá khỏi danh mục là vô nghĩa (lần load
                    sau nó tự hiện lại), backend cũng chặn -> không hiện nút. */}
                {!doc.source_file && (
                  <button onClick={() => onDelete(doc)} className="btn btn-sm btn-ghost hover:text-rose-700">
                    <Trash2 size={14} />
                    Xoá
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
