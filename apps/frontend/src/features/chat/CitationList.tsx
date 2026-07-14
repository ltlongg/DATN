import { useState } from "react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { groupCitations, type CitationChip } from "@/features/chat/groupCitations";
import { SourceModal } from "@/features/chat/SourceModal";
import type { Citation } from "@/types";

const NO_QUOTE_HINT = "Nhấn để xem nguồn";

/**
 * Khối Nguồn dưới câu trả lời — xem docs/plan/citation-viewer-plan.md §3.
 *
 * KHÔNG hiện tên file (cả kho chỉ có 1 file -> in ra là rác) và KHÔNG hiện số dòng (ở danh
 * sách thì "375-378" chẳng nói lên gì; số dòng chỉ có nghĩa khi đứng cạnh full text trong
 * SourceModal). Bỏ hai thứ đó thì 2 citation cùng mục trông y hệt nhau -> phải gộp theo mục,
 * mỗi chunk còn lại một chip `[n]`: hover ra trích đoạn, nhấn ra toàn văn.
 */
function ChipButton({ chip, onSelect }: { chip: CitationChip; onSelect: () => void }) {
  const quote = chip.citation.quote;
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <button
          type="button"
          onClick={onSelect}
          className="rounded border border-paper-border px-1.5 py-0.5 font-medium text-ink-soft transition-colors hover:border-brand hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand/30"
        >
          [{chip.n}]
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="top"
          sideOffset={6}
          collisionPadding={12}
          className="z-50 max-w-sm rounded-md bg-ink px-3 py-2 text-xs leading-relaxed text-white shadow-md"
        >
          {quote ? `“${quote}”` : NO_QUOTE_HINT}
          <Tooltip.Arrow className="fill-ink" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

export function CitationList({ citations }: { citations: Citation[] }) {
  const [selected, setSelected] = useState<Citation | null>(null);
  if (citations.length === 0) return null;
  const { groups, commonPath } = groupCitations(citations);

  return (
    <div className="mt-3 space-y-2 border-t border-paper-border pt-3">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-wide text-ink-soft">Nguồn</p>
        <p className="text-xs text-ink-soft">
          {citations.length} trích đoạn
          {groups.length > 1 && ` · ${groups.length} mục`}
        </p>
      </div>

      <Tooltip.Provider delayDuration={200}>
        <ul className="space-y-1.5">
          {groups.map((group, i) => (
            <li key={i} className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-xs">
              <span className="text-ink">{group.title}</span>
              <span className="flex gap-1">
                {group.chips.map((chip) => (
                  <ChipButton
                    key={chip.n}
                    chip={chip}
                    onSelect={() => setSelected(chip.citation)}
                  />
                ))}
              </span>
            </li>
          ))}
        </ul>
      </Tooltip.Provider>

      {commonPath.length > 0 && (
        <p className="border-t border-paper-border pt-2 text-xs text-ink-soft">
          {commonPath.join(" › ")}
        </p>
      )}

      <SourceModal citation={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
