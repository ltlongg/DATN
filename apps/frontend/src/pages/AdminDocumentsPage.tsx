import { useState } from "react";
import { ApiError } from "@/api/client";
import type { DocumentInput } from "@/api/documents";
import { Modal } from "@/components/Modal";
import { EmptyState } from "@/components/EmptyState";
import { PageHeader } from "@/components/PageHeader";
import { Spinner } from "@/components/Spinner";
import { DocumentFormModal } from "@/features/admin/DocumentFormModal";
import { DocumentTable } from "@/features/admin/DocumentTable";
import {
  useCreateDocument,
  useDeleteDocument,
  useDocuments,
  useUpdateDocument,
} from "@/features/admin/useDocuments";
import type { Document } from "@/types";

export default function AdminDocumentsPage() {
  const { data: documents, isLoading } = useDocuments();
  const createMut = useCreateDocument();
  const updateMut = useUpdateDocument();
  const deleteMut = useDeleteDocument();

  const [form, setForm] = useState<{ open: boolean; doc: Document | null }>({
    open: false,
    doc: null,
  });
  const [formError, setFormError] = useState<string | null>(null);
  const [toDelete, setToDelete] = useState<Document | null>(null);

  async function submitForm(input: DocumentInput) {
    setFormError(null);
    try {
      if (form.doc) await updateMut.mutateAsync({ id: form.doc.id, patch: input });
      else await createMut.mutateAsync(input);
      setForm({ open: false, doc: null });
    } catch (e) {
      setFormError(e instanceof ApiError ? e.message : "Không lưu được tài liệu.");
    }
  }

  async function confirmDelete() {
    if (!toDelete) return;
    try {
      await deleteMut.mutateAsync(toDelete.id);
    } finally {
      setToDelete(null);
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Quản lý tài liệu"
        desc="Danh mục tài liệu nguồn của hệ thống."
        actions={
          <button
            onClick={() => {
              setFormError(null);
              setForm({ open: true, doc: null });
            }}
            className="rounded-md bg-brand px-4 py-2 text-sm text-brand-fg hover:bg-brand-dark"
          >
            + Thêm tài liệu
          </button>
        }
      />

      {isLoading ? (
        <Spinner />
      ) : !documents || documents.length === 0 ? (
        <EmptyState>Chưa có tài liệu nào.</EmptyState>
      ) : (
        <DocumentTable
          documents={documents}
          onEdit={(doc) => {
            setFormError(null);
            setForm({ open: true, doc });
          }}
          onDelete={setToDelete}
        />
      )}

      <DocumentFormModal
        open={form.open}
        initial={form.doc}
        pending={createMut.isPending || updateMut.isPending}
        error={formError}
        onClose={() => setForm({ open: false, doc: null })}
        onSubmit={submitForm}
      />

      <Modal
        open={toDelete !== null}
        onOpenChange={(o) => !o && setToDelete(null)}
        title="Xoá tài liệu"
      >
        <p className="text-sm text-ink-soft">
          Xoá tài liệu “{toDelete?.name}”? Hành động không thể hoàn tác.
        </p>
        <div className="mt-4 flex justify-end gap-2">
          <button
            onClick={() => setToDelete(null)}
            className="rounded-md px-3 py-2 text-sm text-ink-soft hover:text-ink"
          >
            Huỷ
          </button>
          <button
            onClick={confirmDelete}
            disabled={deleteMut.isPending}
            className="rounded-md bg-rose-600 px-4 py-2 text-sm text-white disabled:opacity-60"
          >
            Xoá
          </button>
        </div>
      </Modal>
    </div>
  );
}
