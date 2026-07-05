import { Modal } from "@/components/Modal";
import { lineDiff } from "@/features/prompts/diff";

const ROW_STYLE: Record<string, string> = {
  add: "bg-green-50 text-green-900",
  del: "bg-rose-50 text-rose-900",
  same: "text-ink",
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
    <Modal open={open} onOpenChange={(o) => !o && onClose()} title={title}>
      <div className="max-h-[60vh] overflow-auto rounded-md border border-paper-border">
        <pre className="min-w-full font-mono text-[11px] leading-relaxed">
          {rows.map((r, i) => (
            <div key={i} className={`whitespace-pre-wrap px-2 ${ROW_STYLE[r.type]}`}>
              {SIGN[r.type]} {r.text}
            </div>
          ))}
        </pre>
      </div>
    </Modal>
  );
}
