import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { getMe, updatePreferences } from "@/api/auth";
import { Modal } from "@/components/Modal";
import { useAuthStore } from "@/store/authStore";

const meKey = ["auth-me"] as const;

/**
 * Cài đặt "Chia sẻ hội thoại". Chỉ mount khi mở (xem AppSidebar), nên mỗi lần mở đều đọc lại
 * /me: user lưu ở localStorage có thể là bản cũ, trước khi có field này.
 */
export function PrivacyModal({ onClose }: { onClose: () => void }) {
  const setUser = useAuthStore((s) => s.setUser);
  const qc = useQueryClient();
  const me = useQuery({ queryKey: meKey, queryFn: getMe });
  const save = useMutation({
    mutationFn: updatePreferences,
    onSuccess: (user) => {
      setUser(user);
      qc.setQueryData(meKey, user);
    },
  });

  return (
    <Modal open onOpenChange={(open) => !open && onClose()} title="Quyền riêng tư">
      <label className="flex items-start gap-3 text-sm text-ink">
        <input
          type="checkbox"
          className="mt-1"
          checked={me.data?.share_conversations ?? false}
          disabled={!me.data || save.isPending}
          onChange={(e) => save.mutate({ share_conversations: e.target.checked })}
        />
        <span>
          <span className="font-medium">Chia sẻ hội thoại để cải thiện chất lượng trả lời.</span>{" "}
          Quản trị viên được xem nội dung các hội thoại của bạn để phát hiện câu trả lời sai và
          cải thiện kho tri thức. Bạn có thể tắt bất cứ lúc nào.
        </span>
      </label>
      {save.isError && <p className="mt-3 text-sm text-rose-700">Không lưu được, thử lại sau.</p>}
    </Modal>
  );
}
