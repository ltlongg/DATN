import { Save } from "lucide-react";
import { Alert } from "@/components/Alert";
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
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-xl font-semibold text-ink">{detail.title}</h2>
        <span className="font-mono text-xs text-ink-soft">{detail.key}</span>
        <span className="badge badge-neutral text-[10px]">{detail.grp}</span>
        {hasProduction ? (
          <PromptStatusBadge status="production" />
        ) : (
          <span className="badge badge-warning">
            Chưa có bản production — đang dùng hằng trong code
          </span>
        )}
      </div>
      {detail.description && <p className="mt-1.5 text-sm text-ink-soft">{detail.description}</p>}

      <label htmlFor="prompt-content" className="label mt-5">
        Nội dung system prompt
      </label>
      <textarea
        id="prompt-content"
        value={content}
        onChange={(e) => onContentChange(e.target.value)}
        spellCheck={false}
        wrap="off"
        className="input min-h-[360px] flex-1 resize-y p-3 font-mono text-xs leading-relaxed"
      />

      <label htmlFor="prompt-note" className="label mt-4">
        Ghi chú thay đổi (vì sao?)
      </label>
      <input
        id="prompt-note"
        value={note}
        onChange={(e) => onNoteChange(e.target.value)}
        placeholder="vd: thêm quy tắc trích dẫn nguồn"
        className="input"
      />

      {error && (
        <div className="mt-3">
          <Alert>{error}</Alert>
        </div>
      )}

      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <button onClick={onSave} disabled={!dirty || pending} className="btn btn-primary">
          <Save size={16} />
          Lưu & áp dụng
        </button>
      </div>
    </div>
  );
}
