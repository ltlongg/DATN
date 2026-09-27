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
    <div className="space-y-3">
      {groups.map((g) => (
        <div key={g}>
          <p className="section-title px-3 pb-1.5 pt-2 text-[11px]">
            {GROUP_LABELS[g] ?? g}
          </p>
          <ul className="space-y-0.5">
            {(byGroup.get(g) ?? []).map((p) => {
              const active = p.key === selectedKey;
              return (
                <li key={p.key}>
                  <button
                    onClick={() => onSelect(p.key)}
                    className={`item-row py-2 ${active ? "item-row-active" : ""}`}
                  >
                    <span
                      className={`block text-sm font-medium ${active ? "text-brand-dark" : "text-ink"}`}
                    >
                      {p.title}
                    </span>
                    <span className="block font-mono text-[11px] text-ink-soft">
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
