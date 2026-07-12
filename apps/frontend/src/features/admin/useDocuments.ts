import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createDocument,
  deleteDocument,
  listDocuments,
  listKbSources,
  updateDocument,
  type DocumentInput,
} from "@/api/documents";

export const documentsKey = ["documents"] as const;
export const kbSourcesKey = ["kb-sources"] as const;

export function useDocuments() {
  return useQuery({ queryKey: documentsKey, queryFn: listDocuments });
}

/** Nguồn thật trong kho — dùng cho khối "chưa khai báo" + ô chọn nguồn ở form. */
export function useKbSources() {
  return useQuery({ queryKey: kbSourcesKey, queryFn: listKbSources });
}

/** Mọi mutation đều làm đổi quan hệ document <-> nguồn -> refresh cả hai danh sách. */
function useInvalidateDocs() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: documentsKey });
    qc.invalidateQueries({ queryKey: kbSourcesKey });
  };
}

export function useCreateDocument() {
  const invalidate = useInvalidateDocs();
  return useMutation({
    mutationFn: (input: DocumentInput) => createDocument(input),
    onSuccess: invalidate,
  });
}

export function useUpdateDocument() {
  const invalidate = useInvalidateDocs();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<DocumentInput> }) =>
      updateDocument(id, patch),
    onSuccess: invalidate,
  });
}

export function useDeleteDocument() {
  const invalidate = useInvalidateDocs();
  return useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: invalidate,
  });
}
