import { apiFetch } from "@/api/client";
import type { Conversation, ConversationDetail } from "@/types";

export function listConversations(): Promise<Conversation[]> {
  return apiFetch<Conversation[]>("/api/chat/conversations");
}

export function createConversation(title?: string): Promise<Conversation> {
  return apiFetch<Conversation>("/api/chat/conversations", {
    method: "POST",
    body: { title: title ?? null },
  });
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return apiFetch<ConversationDetail>(`/api/chat/conversations/${id}`);
}

export function renameConversation(id: string, title: string): Promise<Conversation> {
  return apiFetch<Conversation>(`/api/chat/conversations/${id}`, {
    method: "PATCH",
    body: { title },
  });
}

export function deleteConversation(id: string): Promise<void> {
  return apiFetch<void>(`/api/chat/conversations/${id}`, { method: "DELETE" });
}
