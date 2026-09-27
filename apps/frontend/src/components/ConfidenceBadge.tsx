const TONE: Record<string, string> = {
  cao: "badge-success",
  vừa: "badge-warning",
  thấp: "badge-danger",
  "không đủ dữ liệu": "badge-neutral",
};

/** Badge độ tin cậy câu trả lời/sự kiện. Không có confidence -> không render. */
export function ConfidenceBadge({ confidence }: { confidence: string | null | undefined }) {
  if (!confidence) return null;
  return <span className={`badge ${TONE[confidence] ?? "badge-neutral"}`}>{confidence}</span>;
}
