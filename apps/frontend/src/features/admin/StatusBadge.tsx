import type { DocumentStatus } from "@/types";

const TONE: Record<DocumentStatus, string> = {
  draft: "badge-neutral",
  indexing: "badge-warning",
  indexed: "badge-success",
  failed: "badge-danger",
};

const LABELS: Record<DocumentStatus, string> = {
  draft: "Nháp",
  indexing: "Đang index",
  indexed: "Đã index",
  failed: "Lỗi",
};

export function StatusBadge({ status }: { status: DocumentStatus }) {
  return <span className={`badge ${TONE[status]}`}>{LABELS[status]}</span>;
}
