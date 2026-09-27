import { useState } from "react";
import { Plus } from "lucide-react";
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
    <div className="space-y-6">
      <PageHeader
        title="Quản lý tài liệu"
        desc="Tài liệu đã index tự hiện ở đây; số chunk và sự kiện là số đếm thật từ kho tri thức."
        actions={
          <button
            onClick={() => {
              setFormError(null);
              setForm({ open: true, doc: null });
            }}
            className="btn btn-primary"
          >
            <Plus size={16} />
            Thêm tài liệu
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
          Xoá tài liệu “{toDelete?.name}” khỏi danh mục? Hành động không thể hoàn tác.
        </p>
        <div className="mt-6 flex justify-end gap-2">
          <button onClick={() => setToDelete(null)} className="btn btn-secondary">
            Huỷ
          </button>
          <button onClick={confirmDelete} disabled={deleteMut.isPending} className="btn btn-danger">
            Xoá
          </button>
        </div>
      </Modal>
    </div>
  );
}
