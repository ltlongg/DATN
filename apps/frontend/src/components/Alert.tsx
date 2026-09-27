import type { ReactNode } from "react";
import { AlertCircle, AlertTriangle, CheckCircle2 } from "lucide-react";

const TONES = {
  danger: { icon: AlertCircle, cls: "bg-rose-50 text-rose-800 ring-rose-600/15" },
  warning: { icon: AlertTriangle, cls: "bg-amber-50 text-amber-800 ring-amber-600/20" },
  success: { icon: CheckCircle2, cls: "bg-emerald-50 text-emerald-800 ring-emerald-600/15" },
} as const;

/** Hộp thông báo ngắn (lỗi form, lưu thành công…). Lỗi dùng role="alert" để trình đọc màn
 * hình đọc ngay; còn lại là role="status". */
export function Alert({
  tone = "danger",
  children,
}: {
  tone?: keyof typeof TONES;
  children: ReactNode;
}) {
  const { icon: Icon, cls } = TONES[tone];
  return (
    <div
      role={tone === "danger" ? "alert" : "status"}
      className={`flex items-start gap-2 rounded-lg px-3 py-2.5 text-sm ring-1 ring-inset ${cls}`}
    >
      <Icon size={16} className="mt-0.5 shrink-0" aria-hidden />
      <div className="min-w-0">{children}</div>
    </div>
  );
}
