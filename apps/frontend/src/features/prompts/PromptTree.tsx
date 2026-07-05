import type { PromptListItem } from "@/types/prompt";

const GROUP_ORDER = ["ONLINE", "GUARDRAIL", "INDEXING"] as const;
const GROUP_LABELS: Record<string, string> = {
  ONLINE: "Online — mỗi câu trả lời",
  GUARDRAIL: "Guardrail",
  INDEXING: "Indexing — offline (chưa nối runtime)",
};

/** Cột trái: danh sách prompt theo nhóm, chọn 1 để mở editor. */
export function PromptTree({
  items,
  selectedKey,
  onSelect,
}: {
  items: PromptListItem[];
  selectedKey: string | null;
  onSelect: (key: string) => void;
}) {
  const byGroup = new Map<string, PromptListItem[]>();
  for (const p of items) {
    const g = byGroup.get(p.grp) ?? [];
    g.push(p);
    byGroup.set(p.grp, g);
  }
  const groups = [...GROUP_ORDER.filter((g) => byGroup.has(g)), ...[...byGroup.keys()].filter((g) => !GROUP_ORDER.includes(g as (typeof GROUP_ORDER)[number]))];

  return (
    <div className="space-y-4">
      {groups.map((g) => (
        <div key={g}>
          <p className="px-1 pb-1 text-[10px] font-semibold uppercase tracking-wide text-ink-soft/70">
            {GROUP_LABELS[g] ?? g}
          </p>
          <ul className="space-y-1">
            {(byGroup.get(g) ?? []).map((p) => {
              const active = p.key === selectedKey;
              return (
                <li key={p.key}>
                  <button
                    onClick={() => onSelect(p.key)}
                    className={`w-full rounded-md px-2 py-1.5 text-left ${
                      active ? "bg-brand text-brand-fg" : "hover:bg-paper"
                    }`}
                  >
                    <span className="block text-sm font-medium">{p.title}</span>
                    <span className={`block text-[11px] ${active ? "text-brand-fg/80" : "text-ink-soft"}`}>
                      {p.key} · v{p.active_version_no ?? "—"} · {p.version_count} bản
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}
