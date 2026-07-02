import { apiFetch } from "@/api/client";
import type { Document, DocumentStatus } from "@/types";

export interface DocumentInput {
  name: string;
  type: string;
  status: DocumentStatus;
  chunk_count: number;
}

export function listDocuments(): Promise<Document[]> {
  return apiFetch<Document[]>("/api/admin/documents");
}

export function createDocument(input: DocumentInput): Promise<Document> {
  return apiFetch<Document>("/api/admin/documents", { method: "POST", body: input });
}

export function updateDocument(
  id: string,
  patch: Partial<DocumentInput>,
): Promise<Document> {
  return apiFetch<Document>(`/api/admin/documents/${id}`, { method: "PATCH", body: patch });
}

export function deleteDocument(id: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/api/admin/documents/${id}`, { method: "DELETE" });
}
