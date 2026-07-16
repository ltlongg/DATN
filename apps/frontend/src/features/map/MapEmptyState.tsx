/** Honest fallback duy nhất còn lại của bản đồ: thiếu Google Maps API key.
 * (Không còn empty-state "chưa có toạ độ" — base map trống là trạng thái hợp lệ
 * khi map làm nền trang, plan §2.3.) */
export function MapEmptyState() {
  return (
    <div className="flex h-full items-center justify-center bg-paper p-6 text-center text-sm text-ink-soft">
      Chưa cấu hình Google Maps API key.
    </div>
  );
}
