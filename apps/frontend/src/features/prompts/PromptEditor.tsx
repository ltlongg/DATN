import { PromptStatusBadge } from "@/features/prompts/PromptStatusBadge";
import type { PromptDetail } from "@/types/prompt";

/** Cột giữa: sửa content + note, lưu là tạo version mới và đẩy production ngay. */
export function PromptEditor({
  detail,
  content,
  note,
  dirty,
  pending,
  error,
  onContentChange,
  onNoteChange,
  onSave,
}: {
  detail: PromptDetail;
  content: string;
  note: string;
  dirty: boolean;
  pending: boolean;
  error: string | null;
  onContentChange: (v: string) => void;
  onNoteChange: (v: string) => void;
  onSave: () => void;
}) {
  const hasProduction = detail.production_content !== null;
  return (
    <div className="flex h-full flex-col">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <h3 className="text-lg font-semibold text-ink">{detail.title}</h3>
        <span className="text-xs text-ink-soft">{detail.key}</span>
        <span className="rounded-full border border-paper-border px-2 py-0.5 text-[10px] text-ink-soft">
          {detail.grp}
        </span>
        {hasProduction ? (
          <PromptStatusBadge status="production" />
        ) : (
          <span className="text-[11px] text-amber-700">Chưa có bản production — đang dùng hằng trong code</span>
        )}
      </div>
      {detail.description && <p className="mb-2 text-xs text-ink-soft">{detail.description}</p>}

      <label className="mb-1 text-xs font-medium text-ink-soft">Nội dung system prompt</label>
      <textarea
        value={content}
        onChange={(e) => onContentChange(e.target.value)}
        spellCheck={false}
        wrap="off"
        className="min-h-[320px] flex-1 resize-y rounded-md border border-paper-border bg-paper-card p-3 font-mono text-xs leading-relaxed text-ink outline-none focus:border-brand"
      />

      <label className="mb-1 mt-3 text-xs font-medium text-ink-soft">
        Ghi chú thay đổi (vì sao?)
      </label>
      <input
        value={note}
        onChange={(e) => onNoteChange(e.target.value)}
        placeholder="vd: thêm quy tắc trích dẫn nguồn"
        className="rounded-md border border-paper-border bg-paper-card px-3 py-2 text-sm text-ink outline-none focus:border-brand"
      />

      {error && <p className="mt-2 text-sm text-rose-700">{error}</p>}

      <div className="mt-3 flex flex-wrap justify-end gap-2">
        <button
          onClick={onSave}
          disabled={!dirty || pending}
          className="rounded-md bg-brand px-4 py-2 text-sm text-brand-fg hover:bg-brand-dark disabled:opacity-50"
        >
          Lưu & áp dụng
        </button>
      </div>
    </div>
  );
}
