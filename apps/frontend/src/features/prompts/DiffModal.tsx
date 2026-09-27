import { Modal } from "@/components/Modal";
import { lineDiff } from "@/features/prompts/diff";

const ROW_STYLE: Record<string, string> = {
  add: "bg-emerald-50 text-emerald-900",
  del: "bg-rose-50 text-rose-900",
  same: "text-ink-soft",
};
const SIGN: Record<string, string> = { add: "+", del: "-", same: " " };

/** So sánh 2 nội dung prompt theo dòng (unified diff). `oldText` = bản production hiện hành,
 * `newText` = version được chọn. */
export function DiffModal({
  open,
  title,
  oldText,
  newText,
  onClose,
}: {
  open: boolean;
  title: string;
  oldText: string;
  newText: string;
  onClose: () => void;
}) {
  const rows = open ? lineDiff(oldText, newText) : [];
  return (
    <Modal open={open} onOpenChange={(o) => !o && onClose()} title={title} size="lg">
      <div className="max-h-[60vh] overflow-auto rounded-lg border border-paper-border">
        <pre className="min-w-full py-1 font-mono text-[11px] leading-relaxed">
          {rows.map((r, i) => (
            <div key={i} className={`whitespace-pre-wrap px-3 ${ROW_STYLE[r.type]}`}>
              {SIGN[r.type]} {r.text}
            </div>
          ))}
        </pre>
      </div>
    </Modal>
  );
}
