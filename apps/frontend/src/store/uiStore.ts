import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { resolveStorage } from "@/store/storage";

/** UI state toàn app, persist localStorage. Hiện chỉ có trạng thái đóng/mở sidebar nav. */
interface UiState {
  sidebarOpen: boolean;
  toggleSidebar: () => void;
}

export const useUiStore = create<UiState>()(
  persist(
    (set) => ({
      sidebarOpen: true,
      toggleSidebar: () => set((s) => ({ sidebarOpen: !s.sidebarOpen })),
    }),
    { name: "vfs-ui", storage: createJSONStorage(resolveStorage) },
  ),
);
