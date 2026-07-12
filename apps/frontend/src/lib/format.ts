/**
 * TTFT (ms) -> chuỗi ngắn hiển thị: dưới 1 giây thì "850ms", từ 1 giây trở lên "2.5s".
 * null/undefined (message user, hoặc stream hỏng trước token đầu) -> "—".
 */
export function formatTtft(ms: number | null | undefined): string {
  if (ms === null || ms === undefined || !Number.isFinite(ms)) return "—";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/** Định dạng ISO timestamp -> "dd/mm/yyyy HH:MM" (vi-VN). Chuỗi rỗng nếu không hợp lệ. */
export function formatDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
