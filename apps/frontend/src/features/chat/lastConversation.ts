import { useEffect, useRef } from "react";
import { getConversation } from "@/api/chat";
import type { Message } from "@/types";
import { resolveStorage } from "@/store/storage";

/**
 * Nhớ phiên đang mở để lần sau vào lại khu hỏi đáp không rơi vào màn hình trắng.
 *
 * `useChat` giữ hội thoại trong state cục bộ của AskPage, nên rời sang trang khác rồi quay
 * lại là dựng mới với `conversationId = null` — dữ liệu vẫn còn nguyên trong DB, chỉ là
 * không ai chọn lại giúp. Đây là chỗ nhớ hộ id đó.
 *
 * Key gắn theo user: máy dùng chung nhiều tài khoản thì mỗi người mở lại phiên của mình,
 * không đòi phiên của người trước (gọi API sẽ 403/404, nhưng tránh hẳn vẫn hơn).
 */
const PREFIX = "vfs-last-conversation:";

export function readLastConversation(userId: string | undefined): string | null {
  if (!userId) return null;
  return resolveStorage().getItem(PREFIX + userId);
}

/** `id = null` (phiên mới rỗng, chưa gửi câu nào) -> xoá, khỏi mở lại phiên vừa bỏ. */
export function writeLastConversation(userId: string | undefined, id: string | null): void {
  if (!userId) return;
  const storage = resolveStorage();
  if (id) storage.setItem(PREFIX + userId, id);
  else storage.removeItem(PREFIX + userId);
}

/**
 * Nạp lại phiên đã nhớ, MỘT lần cho mỗi lần vào trang. Chỉ tự bấm hộ đúng cú click mà thanh
 * bên vẫn làm: `getConversation` rồi `restore`.
 *
 * Cố tình KHÔNG huỷ theo cleanup của effect. StrictMode (dev) chạy effect -> cleanup ->
 * effect lại trên cùng instance; cờ huỷ đặt ở cleanup sẽ giết lần fetch duy nhất (lần chạy
 * thứ hai đã bị `restored` chặn) và phiên không bao giờ được khôi phục. Hai lá chắn còn lại
 * đủ việc: `restored` chống chạy hai lần, `busy()` chống đè lên phiên người dùng vừa tự mở.
 *
 * `busy` là hàm chứ không phải giá trị vì được đọc SAU khi await — giá trị bắt lúc effect
 * chạy đã cũ.
 */
export function useRestoreLastConversation(
  userId: string | undefined,
  busy: () => boolean,
  restore: (id: string, messages: Message[]) => void,
): { markHandled: () => void } {
  const restored = useRef(false);
  const busyRef = useRef(busy);
  busyRef.current = busy;
  const restoreRef = useRef(restore);
  restoreRef.current = restore;

  useEffect(() => {
    if (restored.current || !userId) return;
    const saved = readLastConversation(userId);
    if (!saved) return;
    restored.current = true;
    void (async () => {
      try {
        const detail = await getConversation(saved);
        if (!busyRef.current()) restoreRef.current(saved, detail.messages);
      } catch {
        writeLastConversation(userId, null); // phiên đã bị xoá -> quên đi, đừng đòi lại
      }
    })();
  }, [userId]);

  // Người dùng chủ động mở phiên mới -> đừng khôi phục đè lên nữa.
  return { markHandled: () => void (restored.current = true) };
}
