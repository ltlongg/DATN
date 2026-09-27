import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getMe } from "@/api/auth";
import { useAuthStore } from "@/store/authStore";
import type { User } from "@/types";

const meKey = ["auth-me"] as const;

/**
 * Hồ sơ người dùng cho trang Cài đặt. Luôn đọc lại /me thay vì tin user trong localStorage:
 * bản lưu có thể cũ, trước khi có field mới (`share_conversations`, `has_password`).
 */
export function useMe() {
  return useQuery({ queryKey: meKey, queryFn: getMe });
}

/** Sau khi lưu thành công: đồng bộ cả cache /me lẫn auth store (sidebar đọc tên từ store). */
export function useApplyUser() {
  const setUser = useAuthStore((s) => s.setUser);
  const qc = useQueryClient();
  return (user: User) => {
    setUser(user);
    qc.setQueryData(meKey, user);
  };
}
