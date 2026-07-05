import { apiFetch } from "@/api/client";
import type {
  CreateVersionInput,
  PromptDetail,
  PromptListItem,
  PromptVersionContent,
  PromptVersionMeta,
} from "@/types/prompt";

export function listPrompts(): Promise<PromptListItem[]> {
  return apiFetch<PromptListItem[]>("/api/admin/prompts");
}

export function getPrompt(key: string): Promise<PromptDetail> {
  return apiFetch<PromptDetail>(`/api/admin/prompts/${key}`);
}

export function getPromptVersion(key: string, versionNo: number): Promise<PromptVersionContent> {
  return apiFetch<PromptVersionContent>(`/api/admin/prompts/${key}/versions/${versionNo}`);
}

export function createPromptVersion(
  key: string,
  input: CreateVersionInput,
): Promise<PromptVersionMeta> {
  return apiFetch<PromptVersionMeta>(`/api/admin/prompts/${key}/versions`, {
    method: "POST",
    body: input,
  });
}

export function promotePromptVersion(key: string, versionNo: number): Promise<PromptDetail> {
  return apiFetch<PromptDetail>(`/api/admin/prompts/${key}/versions/${versionNo}/promote`, {
    method: "POST",
  });
}
