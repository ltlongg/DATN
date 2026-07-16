import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { resolveStorage } from "@/store/storage";

/** `float` = map nền toàn màn hình + chat nổi (mặc định); `split` = chat 1 bên, map 1 bên. */
export type LayoutMode = "float" | "split";

/**
 * UI state khung chat. `selectedEventId` là NGUỒN SỰ THẬT liên kết map <-> timeline:
 * click marker, click timeline row, hay bước trình chiếu đều set nó — cả hai bên
 * highlight theo. `tourPlaying` để bản đồ biết đang trình chiếu mà dí camera vào
 * điểm đang kể (thay vì chỉ pan hiền như lúc user tự click).
 * `debugOpen` lưu trạng thái gập/mở panel debug theo từng message (admin).
 *
 * CHỈ `layoutMode` persist (lựa chọn bố cục là preference của user, phải sống qua
 * reload); phần còn lại thuộc về một lượt hỏi đáp -> ephemeral.
 */
interface ChatUiState {
  layoutMode: LayoutMode;
  convDrawerOpen: boolean;
  vizPanelOpen: boolean;
  selectedEventId: string | null;
  tourPlaying: boolean;
  debugOpen: Record<string, boolean>;
  setLayoutMode: (mode: LayoutMode) => void;
  setConvDrawerOpen: (open: boolean) => void;
  openViz: () => void;
  closeViz: () => void;
  setSelectedEvent: (eventId: string | null) => void;
  setTourPlaying: (playing: boolean) => void;
  toggleDebug: (messageId: string) => void;
}

export const useChatUiStore = create<ChatUiState>()(
  persist(
    (set) => ({
      layoutMode: "float",
      convDrawerOpen: false,
      vizPanelOpen: false,
      selectedEventId: null,
      tourPlaying: false,
      debugOpen: {},
      setLayoutMode: (layoutMode) => set({ layoutMode }),
      setConvDrawerOpen: (convDrawerOpen) => set({ convDrawerOpen }),
      openViz: () => set({ vizPanelOpen: true }),
      closeViz: () => set({ vizPanelOpen: false }),
      setSelectedEvent: (selectedEventId) => set({ selectedEventId }),
      setTourPlaying: (tourPlaying) => set({ tourPlaying }),
      toggleDebug: (messageId) =>
        set((s) => ({ debugOpen: { ...s.debugOpen, [messageId]: !s.debugOpen[messageId] } })),
    }),
    {
      name: "vfs-chat-ui",
      storage: createJSONStorage(resolveStorage),
      partialize: (s) => ({ layoutMode: s.layoutMode }),
    },
  ),
);
