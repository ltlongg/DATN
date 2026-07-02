import { create } from "zustand";

/**
 * UI state khung chat (không persist). `selectedEventId` là NGUỒN SỰ THẬT liên kết
 * map <-> timeline: click marker hoặc timeline row đều set nó, cả hai highlight theo.
 * `debugOpen` lưu trạng thái gập/mở panel debug theo từng message (admin).
 */
interface ChatUiState {
  vizPanelOpen: boolean;
  selectedEventId: string | null;
  debugOpen: Record<string, boolean>;
  openViz: () => void;
  closeViz: () => void;
  setSelectedEvent: (eventId: string | null) => void;
  toggleDebug: (messageId: string) => void;
  reset: () => void;
}

export const useChatUiStore = create<ChatUiState>((set) => ({
  vizPanelOpen: false,
  selectedEventId: null,
  debugOpen: {},
  openViz: () => set({ vizPanelOpen: true }),
  closeViz: () => set({ vizPanelOpen: false }),
  setSelectedEvent: (eventId) => set({ selectedEventId: eventId }),
  toggleDebug: (messageId) =>
    set((s) => ({ debugOpen: { ...s.debugOpen, [messageId]: !s.debugOpen[messageId] } })),
  reset: () => set({ vizPanelOpen: false, selectedEventId: null, debugOpen: {} }),
}));
