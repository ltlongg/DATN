/**
 * Honest fallback khi không có marker. Hiện tại gazetteer đang hoãn -> markers luôn rỗng,
 * nên đây là trạng thái thường gặp của bản đồ (KHÔNG phải lỗi).
 */
export function MapEmptyState({ reason }: { reason?: "no-key" | "no-markers" }) {
  const message =
    reason === "no-key"
      ? "Chưa cấu hình Google Maps API key."
      : "Chưa có dữ liệu toạ độ cho các sự kiện này.";
  return (
    <div className="flex h-full items-center justify-center bg-paper p-6 text-center text-sm text-ink-soft">
      {message}
    </div>
  );
}
