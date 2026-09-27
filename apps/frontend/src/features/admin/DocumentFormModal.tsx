import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/Alert";
import { Field } from "@/components/Field";
import { Modal } from "@/components/Modal";
import type { DocumentInput } from "@/api/documents";
import type { Document, DocumentStatus } from "@/types";

const STATUSES: DocumentStatus[] = ["draft", "indexing", "indexed", "failed"];

/** Form tạo/sửa tài liệu.
 *
 * KHÔNG có ô "Số chunk" (đếm thật từ kho) lẫn ô chọn nguồn (tài liệu đã index tự hiện ở
 * danh mục). Form này chỉ đặt phần thông tin do người quản trị quyết: tên, loại, trạng thái.
 */
export function DocumentFormModal({
  open,
  initial,
  pending,
  error,
  onClose,
  onSubmit,
}: {
  open: boolean;
  initial: Document | null;
  pending: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (input: DocumentInput) => void;
}) {
  const [name, setName] = useState("");
  const [type, setType] = useState("markdown");
  const [status, setStatus] = useState<DocumentStatus>("draft");

  useEffect(() => {
    if (open) {
      setName(initial?.name ?? "");
      setType(initial?.type ?? "markdown");
      setStatus(initial?.status ?? "draft");
    }
  }, [open, initial]);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (name.trim() === "") return;
    onSubmit({ name: name.trim(), type: type.trim() || "markdown", status });
  }

  return (
    <Modal
      open={open}
      onOpenChange={(o) => !o && onClose()}
      title={initial ? "Sửa tài liệu" : "Thêm tài liệu"}
    >
      <form onSubmit={submit} className="space-y-4">
        <Field label="Tên hiển thị">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="input"
          />
        </Field>
        <Field label="Loại">
          <input
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="input"
          />
        </Field>
        <Field label="Trạng thái">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as DocumentStatus)}
            className="input"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>

        {initial?.source_file && (
          <p className="rounded-lg bg-paper-sunken px-3 py-2.5 text-xs leading-relaxed text-ink-soft">
            Nguồn trong kho: <code>{initial.source_file}</code> —{" "}
            {initial.chunk_count.toLocaleString("vi-VN")} chunk,{" "}
            {initial.event_count.toLocaleString("vi-VN")} sự kiện. Nguồn là khóa nối, không đổi
            được.
          </p>
        )}

        {error && <Alert>{error}</Alert>}

        <div className="flex justify-end gap-2 pt-2">
          <button type="button" onClick={onClose} className="btn btn-secondary">
            Huỷ
          </button>
          <button type="submit" disabled={pending} className="btn btn-primary">
            {pending ? "Đang lưu…" : "Lưu"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
