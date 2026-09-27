const TONE: Record<string, string> = {
  production: "badge-success",
  archived: "badge-neutral",
};
const LABELS: Record<string, string> = {
  production: "PRODUCTION",
  archived: "ARCHIVED",
};

export function PromptStatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge text-[10px] tracking-wide ${TONE[status] ?? "badge-neutral"}`}>
      {LABELS[status] ?? status.toUpperCase()}
    </span>
  );
}
