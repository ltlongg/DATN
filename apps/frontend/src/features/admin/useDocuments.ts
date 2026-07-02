import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createDocument,
  deleteDocument,
  listDocuments,
  updateDocument,
  type DocumentInput,
} from "@/api/documents";

export const documentsKey = ["documents"] as const;

export function useDocuments() {
  return useQuery({ queryKey: documentsKey, queryFn: listDocuments });
}

export function useCreateDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: DocumentInput) => createDocument(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: documentsKey }),
  });
}

export function useUpdateDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, patch }: { id: string; patch: Partial<DocumentInput> }) =>
      updateDocument(id, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: documentsKey }),
  });
}

export function useDeleteDocument() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteDocument(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: documentsKey }),
  });
}
