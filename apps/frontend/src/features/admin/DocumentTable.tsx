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
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-paper-border text-left text-ink-soft">
            <th className="py-2 pr-4 font-medium">Tên</th>
            <th className="py-2 pr-4 font-medium">Nguồn trong kho</th>
            <th className="py-2 pr-4 font-medium">Loại</th>
            <th className="py-2 pr-4 font-medium">Trạng thái</th>
            <th className="py-2 pr-4 text-right font-medium">Số chunk</th>
            <th className="py-2 pr-4 text-right font-medium">Sự kiện</th>
            <th className="py-2 pr-4 font-medium">Ngày tạo</th>
            <th className="py-2 font-medium"></th>
          </tr>
        </thead>
        <tbody>
          {documents.map((doc) => (
            <tr key={doc.id} className="border-b border-paper-border">
              <td className="py-2 pr-4 text-ink">{doc.name}</td>
              <td className="py-2 pr-4">
                {doc.source_file ? (
                  <code className="text-xs text-ink-soft">{doc.source_file}</code>
                ) : (
                  <span className="text-xs text-ink-soft">Chưa gắn nguồn</span>
                )}
              </td>
              <td className="py-2 pr-4 text-ink-soft">{doc.type}</td>
              <td className="py-2 pr-4">
                <StatusBadge status={doc.status} />
              </td>
              <td className="py-2 pr-4 text-right tabular-nums text-ink-soft">
                {doc.source_file ? doc.chunk_count.toLocaleString("vi-VN") : "—"}
              </td>
              <td className="py-2 pr-4 text-right tabular-nums text-ink-soft">
                {doc.source_file ? doc.event_count.toLocaleString("vi-VN") : "—"}
              </td>
              <td className="py-2 pr-4 text-ink-soft">{formatDateTime(doc.created_at)}</td>
              <td className="py-2 text-right whitespace-nowrap">
                <button
                  onClick={() => onEdit(doc)}
                  className="mr-3 text-ink-soft hover:text-brand"
                >
                  Sửa
                </button>
                {/* Tài liệu còn chunk trong kho: xoá khỏi danh mục là vô nghĩa (lần load
                    sau nó tự hiện lại), backend cũng chặn -> không hiện nút. */}
                {!doc.source_file && (
                  <button
                    onClick={() => onDelete(doc)}
                    className="text-ink-soft hover:text-rose-700"
                  >
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
