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
