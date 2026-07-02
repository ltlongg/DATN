import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createConversation, listConversations } from "@/api/chat";

export const conversationsKey = ["conversations"] as const;

export function useConversations() {
  return useQuery({ queryKey: conversationsKey, queryFn: listConversations });
}

export function useCreateConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (title?: string) => createConversation(title),
    onSuccess: () => qc.invalidateQueries({ queryKey: conversationsKey }),
  });
}
