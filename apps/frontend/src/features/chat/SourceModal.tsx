import { useQuery } from "@tanstack/react-query";
import { getSource } from "@/api/chat";
import { Modal } from "@/components/Modal";
import { Spinner } from "@/components/Spinner";
import type { Citation } from "@/types";

/**
 * Toàn văn nguồn khi user nhấn chip `[n]` — xem docs/plan/citation-viewer-plan.md §5 Pha 3.
 *
 * Fetch LƯỜI (chỉ khi mở) và cache theo chunk_id: full text ~700 token, không đáng nhồi vào
 * mọi citation của mọi message. Tiêu đề lấy từ `citation` đang có sẵn nên hiện ngay, không
 * phải chờ mạng; chỉ phần thân mới đợi.
 */
export function SourceModal({
  citation,
  onClose,
}: {
  citation: Citation | null;
  onClose: () => void;
}) {
  const chunkId = citation?.chunk_id;
  const { data, isPending, isError } = useQuery({
    queryKey: ["source", chunkId],
    queryFn: () => getSource(chunkId as string),
    enabled: chunkId !== undefined,
  });

  if (!citation) return null;

  const path = citation.heading_path;
  const title = path.at(-1) ?? "Nguồn";
  const breadcrumb = path.slice(0, -1).join(" › ");
  // Số dòng CHỈ hiện ở đây: cạnh toàn văn thì nó là provenance thật, ở danh sách nguồn thì vô nghĩa.
  const lines =
    data?.start_line != null && data.end_line != null
      ? `dòng ${data.start_line}–${data.end_line}`
      : null;

  return (
    <Modal open onOpenChange={(open) => !open && onClose()} title={title} size="lg">
      {(breadcrumb || lines) && (
        <p className="-mt-2 mb-3 text-xs text-ink-soft">
          {[breadcrumb, lines].filter(Boolean).join(" · ")}
        </p>
      )}

      {isPending && <Spinner label="Đang tải nguồn…" />}
      {isError && (
        <p className="text-sm text-brand">
          Không tải được nguồn này. Có thể đoạn tài liệu đã bị gỡ khỏi kho tri thức.
        </p>
      )}
      {data && (
        <div className="max-h-[60vh] overflow-y-auto whitespace-pre-wrap rounded-md border border-paper-border bg-paper p-4 text-sm leading-relaxed text-ink">
          {data.text}
        </div>
      )}
    </Modal>
  );
}
