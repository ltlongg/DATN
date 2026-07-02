import type { DocumentStatus } from "@/types";

const STYLES: Record<DocumentStatus, string> = {
  draft: "bg-gray-100 text-gray-700",
  indexing: "bg-amber-100 text-amber-800",
  indexed: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
};

const LABELS: Record<DocumentStatus, string> = {
  draft: "Nháp",
  indexing: "Đang index",
  indexed: "Đã index",
  failed: "Lỗi",
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return (
    <span
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}
