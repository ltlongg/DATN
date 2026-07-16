import { useEffect, type ReactNode } from "react";
import { X } from "lucide-react";

/**
 * Drawer trượt trái chứa danh sách phiên — dùng ở layout `float`, nơi sidebar phiên
 * không thể chiếm chỗ cố định (map là nền). Đóng bằng backdrop, nút ✕ hoặc Escape.
 */
export function ConversationDrawer({
  open,
  onClose,
  children,
}: {
  open: boolean;
  onClose: () => void;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="absolute inset-0 z-40 flex">
      <div className="relative flex h-full shadow-2xl">
        {children}
        <button
          onClick={onClose}
          aria-label="Đóng danh sách"
          className="absolute right-2 top-2 rounded-md p-1 text-ink-soft hover:bg-paper hover:text-brand"
        >
          <X size={16} />
        </button>
      </div>
      {/* backdrop: click ra ngoài để đóng */}
      <button
        onClick={onClose}
        aria-label="Đóng danh sách"
        tabIndex={-1}
        className="h-full flex-1 cursor-default bg-ink/20"
      />
    </div>
  );
}
