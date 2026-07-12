import { apiFetch } from "@/api/client";
import type { Document, DocumentStatus, KbSource } from "@/types";

/** KHÔNG có `source_file`: tài liệu đã index trong kho tự hiện ở danh mục (backend
 * sync), form chỉ tạo/sửa phần thông tin do người quản trị quyết. */
export interface DocumentInput {
  name: string;
  type: string;
  status: DocumentStatus;
}

export function listDocuments(): Promise<Document[]> {
  return apiFetch<Document[]>("/api/admin/documents");
}

/** Nguồn có thật trong kho tri thức (kể cả nguồn chưa khai báo ở danh mục). */
export function listKbSources(): Promise<KbSource[]> {
  return apiFetch<KbSource[]>("/api/admin/documents/sources");
}

export function createDocument(input: DocumentInput): Promise<Document> {
  return apiFetch<Document>("/api/admin/documents", { method: "POST", body: input });
}

export function updateDocument(id: string, patch: Partial<DocumentInput>): Promise<Document> {
  return apiFetch<Document>(`/api/admin/documents/${id}`, { method: "PATCH", body: patch });
}

export function deleteDocument(id: string): Promise<{ ok: boolean }> {
  return apiFetch<{ ok: boolean }>(`/api/admin/documents/${id}`, { method: "DELETE" });
}
