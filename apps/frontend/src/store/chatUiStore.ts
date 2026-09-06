import { create } from "zustand";

/**
 * UI state khung chat. `selectedEventId` là NGUỒN SỰ THẬT của việc chọn sự kiện: click
 * một mốc trên thanh thời gian hay một bước trình chiếu đều set nó — thanh thời gian
 * highlight theo. `tourPlaying` cho biết đang trình chiếu (tour tự dừng khi user chọn tay).
 *
 * (`debugOpen`/`toggleDebug` đã bỏ cùng DebugPanel 2026-08-01 — trạng thái gập/mở của tầng
 * 2 nay là state cục bộ trong `StepRow`. `layoutMode`/`vizPanelOpen` bỏ cùng bản đồ
 * 2026-09-06 — chỉ còn một bố cục nên không còn preference nào cần nhớ qua reload, store
 * này thành thuần ephemeral, không persist.)
 */
interface ChatUiState {
  selectedEventId: string | null;
  tourPlaying: boolean;
  setSelectedEvent: (eventId: string | null) => void;
  setTourPlaying: (playing: boolean) => void;
}

export const useChatUiStore = create<ChatUiState>()((set) => ({
  selectedEventId: null,
  tourPlaying: false,
  setSelectedEvent: (selectedEventId) => set({ selectedEventId }),
  setTourPlaying: (tourPlaying) => set({ tourPlaying }),
}));
