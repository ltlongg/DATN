const STYLES: Record<string, string> = {
  cao: "bg-emerald-100 text-emerald-800",
  vừa: "bg-amber-100 text-amber-800",
  thấp: "bg-orange-100 text-orange-800",
  "không đủ dữ liệu": "bg-rose-100 text-rose-800",
};

/** Badge độ tin cậy câu trả lời/sự kiện. Không có confidence -> không render. */
export function ConfidenceBadge({ confidence }: { confidence: string | null | undefined }) {
  if (!confidence) return null;
  const cls = STYLES[confidence] ?? "bg-gray-100 text-gray-700";
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${cls}`}>
      {confidence}
    </span>
  );
}
