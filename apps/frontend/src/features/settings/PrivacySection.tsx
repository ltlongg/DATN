import { useMutation } from "@tanstack/react-query";
import { updatePreferences } from "@/api/auth";
import { Alert } from "@/components/Alert";
import { SettingsSection } from "@/features/settings/SettingsSection";
import { useApplyUser } from "@/features/settings/useMe";
import type { User } from "@/types";

/** Cài đặt "Chia sẻ hội thoại" — lưu ngay khi bật/tắt, không cần nút Lưu. */
export function PrivacySection({ user }: { user: User }) {
  const applyUser = useApplyUser();
  const save = useMutation({ mutationFn: updatePreferences, onSuccess: applyUser });

  return (
    <SettingsSection title="Quyền riêng tư" desc="Quyết định ai được xem nội dung hội thoại của bạn.">
      <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-paper-border p-4 text-sm leading-relaxed text-ink-soft transition-colors hover:bg-paper-sunken/60">
        <input
          type="checkbox"
          className="mt-1 h-4 w-4 shrink-0 accent-brand"
          checked={user.share_conversations}
          disabled={save.isPending}
          onChange={(e) => save.mutate({ share_conversations: e.target.checked })}
        />
        <span>
          <span className="mb-1 block font-medium text-ink">
            Chia sẻ hội thoại để cải thiện chất lượng trả lời.
          </span>
          Quản trị viên được xem nội dung các hội thoại của bạn để phát hiện câu trả lời sai và
          cải thiện kho tri thức. Bạn có thể tắt bất cứ lúc nào.
        </span>
      </label>
      {save.isError && (
        <div className="mt-3">
          <Alert>Không lưu được, thử lại sau.</Alert>
        </div>
      )}
    </SettingsSection>
  );
}
