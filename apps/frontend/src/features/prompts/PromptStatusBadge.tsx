const STYLES: Record<string, string> = {
  production: "bg-green-100 text-green-800",
  archived: "bg-gray-200 text-gray-600",
};
const LABELS: Record<string, string> = {
  production: "PRODUCTION",
  archived: "ARCHIVED",
};

export function PromptStatusBadge({ status }: { status: string }) {
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
        STYLES[status] ?? "bg-gray-200 text-gray-600"
      }`}
    >
      {LABELS[status] ?? status.toUpperCase()}
    </span>
  );
}
