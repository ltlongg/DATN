import { useChatUiStore } from "@/store/chatUiStore";
import type { ChatItem } from "@/features/chat/chatReducer";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex gap-2 text-xs">
      <span className="w-40 shrink-0 text-ink-soft">{label}</span>
      <span className="text-ink">{value}</span>
    </div>
  );
}

/**
 * Panel debug (admin) gập dưới mỗi câu trả lời. Status trace mọc realtime; block "Phân tích"
 * + "Retrieval" chỉ điền khi event `debug` về (gom 1 lần sát cuối — xem backend-additions §1.1),
 * nên hiển thị placeholder tới lúc đó. Ephemeral: xem lượt cũ đã lưu -> không có debug.
 */
export function DebugPanel({ item }: { item: ChatItem }) {
  const open = useChatUiStore((s) => s.debugOpen[item.id] ?? false);
  const toggle = useChatUiStore((s) => s.toggleDebug);

  const bq = item.debug?.build_query;
  const rt = item.debug?.retrieve;

  return (
    <div className="mt-3 border-t border-paper-border pt-2">
      <button
        onClick={() => toggle(item.id)}
        className="text-xs font-medium text-ink-soft hover:text-brand"
      >
        {open ? "▾" : "▸"} Luồng xử lý
      </button>

      {open && (
        <div className="mt-2 space-y-3 rounded-md bg-paper p-3">
          <section>
            <p className="mb-1 text-xs font-semibold text-ink">Chuỗi bước</p>
            {item.statusTrace.length === 0 ? (
              <p className="text-xs text-ink-soft">Chưa có bước nào.</p>
            ) : (
              <ol className="space-y-0.5">
                {item.statusTrace.map((s, i) => {
                  const running = item.streaming && i === item.statusTrace.length - 1;
                  return (
                    <li key={i} className="text-xs text-ink">
                      <span className="text-ink-soft">{running ? "⏳" : "✓"}</span>{" "}
                      <span className="font-medium">{s.node}</span> — {s.msg}
                    </li>
                  );
                })}
              </ol>
            )}
          </section>

          <section>
            <p className="mb-1 text-xs font-semibold text-ink">Phân tích câu hỏi</p>
            {bq ? (
              <div className="space-y-0.5">
                <Row label="Câu viết lại" value={bq.standalone_query ?? "—"} />
                <Row label="Định tuyến" value={bq.route ?? "—"} />
                <Row
                  label="Thực thể nhắc tới"
                  value={
                    bq.mentioned_entities && bq.mentioned_entities.length > 0
                      ? bq.mentioned_entities.join(", ")
                      : "—"
                  }
                />
              </div>
            ) : (
              <p className="text-xs text-ink-soft">Đang xử lý…</p>
            )}
          </section>

          <section>
            <p className="mb-1 text-xs font-semibold text-ink">Truy hồi</p>
            {rt ? (
              <div className="space-y-0.5">
                <Row label="Số chunk" value={rt.chunks ?? 0} />
                <Row label="Ngữ cảnh graph" value={rt.graph_context ?? 0} />
              </div>
            ) : (
              <p className="text-xs text-ink-soft">Đang xử lý…</p>
            )}
          </section>

          <section>
            <p className="mb-1 text-xs font-semibold text-ink">Kết quả</p>
            <div className="space-y-0.5">
              <Row label="Độ tin cậy" value={item.confidence ?? "—"} />
              <Row label="Chế độ truy hồi" value={item.retrievalMode ?? "—"} />
              <Row label="Số nguồn" value={item.citations.length} />
              <Row
                label="Cảnh báo"
                value={item.warnings.length > 0 ? item.warnings.join("; ") : "—"}
              />
              {item.visualization && (
                <Row
                  label="Visualization"
                  value={`${item.visualization.event_count} sự kiện · ${item.visualization.markers.length} marker · ${item.visualization.timeline.length} mốc · ${item.visualization.unplaced_count} thiếu dữ liệu`}
                />
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
