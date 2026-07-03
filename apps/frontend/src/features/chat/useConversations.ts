import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createConversation,
  deleteConversation,
  listConversations,
  renameConversation,
} from "@/api/chat";
import type { Conversation } from "@/types";

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

/** Đổi tên với optimistic update: sửa ngay trong cache, rollback nếu lỗi, reconcile nền. */
export function useRenameConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, title }: { id: string; title: string }) =>
      renameConversation(id, title),
    onMutate: async ({ id, title }) => {
      await qc.cancelQueries({ queryKey: conversationsKey });
      const prev = qc.getQueryData<Conversation[]>(conversationsKey);
      qc.setQueryData<Conversation[]>(conversationsKey, (old) =>
        (old ?? []).map((c) => (c.id === id ? { ...c, title } : c)),
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(conversationsKey, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: conversationsKey }),
  });
}

/** Xóa với optimistic update: bỏ khỏi cache ngay để UI phản hồi tức thì (không chờ 2 lượt
 * mạng), rollback nếu lỗi, reconcile nền. */
export function useDeleteConversation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteConversation(id),
    onMutate: async (id) => {
      await qc.cancelQueries({ queryKey: conversationsKey });
      const prev = qc.getQueryData<Conversation[]>(conversationsKey);
      qc.setQueryData<Conversation[]>(conversationsKey, (old) =>
        (old ?? []).filter((c) => c.id !== id),
      );
      return { prev };
    },
    onError: (_err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(conversationsKey, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: conversationsKey }),
  });
}
