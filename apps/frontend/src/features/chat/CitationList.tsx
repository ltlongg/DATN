import { useState } from "react";
import * as Tooltip from "@radix-ui/react-tooltip";
import { BookOpen } from "lucide-react";
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
          className="rounded-md border border-paper-border bg-paper px-1.5 py-0.5 font-medium tabular-nums text-ink-soft transition-colors hover:border-brand/40 hover:bg-brand-soft hover:text-brand"
        >
          [{chip.n}]
        </button>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          side="top"
          sideOffset={6}
          collisionPadding={12}
          className="z-50 max-w-sm rounded-lg bg-ink px-3 py-2 text-xs leading-relaxed text-white shadow-pop"
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
    <div className="mt-4 space-y-2.5 border-t border-paper-border pt-3">
      <div className="flex items-baseline justify-between gap-3">
        <p className="section-title flex items-center gap-1.5">
          <BookOpen size={13} aria-hidden />
          Nguồn
        </p>
        <p className="text-xs text-ink-faint">
          {citations.length} trích đoạn
          {groups.length > 1 && ` · ${groups.length} mục`}
        </p>
      </div>

      <Tooltip.Provider delayDuration={200}>
        <ul className="space-y-1.5">
          {groups.map((group, i) => (
            <li key={i} className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm">
              <span className="text-ink">{group.title}</span>
              <span className="flex gap-1 text-xs">
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
        <p className="text-xs text-ink-faint">
          {commonPath.join(" › ")}
        </p>
      )}

      <SourceModal citation={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
