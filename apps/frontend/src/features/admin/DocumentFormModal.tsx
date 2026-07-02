import { useEffect, useState, type FormEvent } from "react";
import { Modal } from "@/components/Modal";
import type { DocumentInput } from "@/api/documents";
import type { Document, DocumentStatus } from "@/types";

const STATUSES: DocumentStatus[] = ["draft", "indexing", "indexed", "failed"];

/** Form tạo/sửa tài liệu (metadata mock — KHÔNG upload file, theo scope Module 3). */
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
  const [chunkCount, setChunkCount] = useState(0);

  useEffect(() => {
    if (open) {
      setName(initial?.name ?? "");
      setType(initial?.type ?? "markdown");
      setStatus(initial?.status ?? "draft");
      setChunkCount(initial?.chunk_count ?? 0);
    }
  }, [open, initial]);

  function submit(e: FormEvent) {
    e.preventDefault();
    if (name.trim() === "") return;
    onSubmit({ name: name.trim(), type: type.trim() || "markdown", status, chunk_count: chunkCount });
  }

  return (
    <Modal open={open} onOpenChange={(o) => !o && onClose()} title={initial ? "Sửa tài liệu" : "Thêm tài liệu"}>
      <form onSubmit={submit} className="space-y-3">
        <Field label="Tên">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            className="w-full rounded-md border border-paper-border px-3 py-2 outline-none focus:border-brand"
          />
        </Field>
        <Field label="Loại">
          <input
            value={type}
            onChange={(e) => setType(e.target.value)}
            className="w-full rounded-md border border-paper-border px-3 py-2 outline-none focus:border-brand"
          />
        </Field>
        <Field label="Trạng thái">
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value as DocumentStatus)}
            className="w-full rounded-md border border-paper-border px-3 py-2 outline-none focus:border-brand"
          >
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Số chunk">
          <input
            type="number"
            min={0}
            value={chunkCount}
            onChange={(e) => setChunkCount(Math.max(0, Number(e.target.value)))}
            className="w-full rounded-md border border-paper-border px-3 py-2 outline-none focus:border-brand"
          />
        </Field>

        {error && <p className="text-sm text-rose-700">{error}</p>}

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md px-3 py-2 text-sm text-ink-soft hover:text-ink"
          >
            Huỷ
          </button>
          <button
            type="submit"
            disabled={pending}
            className="rounded-md bg-brand px-4 py-2 text-sm text-brand-fg disabled:opacity-60"
          >
            {pending ? "Đang lưu…" : "Lưu"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium text-ink-soft">{label}</span>
      {children}
    </label>
  );
}
