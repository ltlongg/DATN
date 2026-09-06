import { useCallback, useEffect, useRef, useState } from "react";
import { useChatUiStore } from "@/store/chatUiStore";
import type { TimelineItem } from "@/types";

/** Thời gian dừng ở mỗi sự kiện. Khi cắm text-to-speech: thay điểm hẹn giờ này bằng
 * "đọc xong câu thì đi tiếp" (`utterance.onend`), phần còn lại của engine giữ nguyên. */
export const TOUR_STEP_MS = 2500;

export interface EventTour {
  playing: boolean;
  /** Sự kiện đang được kể — móc sẵn cho text-to-speech đọc `label`/`summary`. */
  currentEvent: TimelineItem | null;
  start: () => void;
  stop: () => void;
}

/**
 * Trình chiếu ("kể") lần lượt các sự kiện của câu trả lời: mỗi bước set
 * `selectedEventId` rồi chờ `TOUR_STEP_MS`. Không tự vẽ gì — map và timeline vốn đã
 * highlight theo `selectedEventId`, nên chỉ cần đẩy id là cả hai bên chạy theo.
 *
 * `events` phải ĐÃ sắp theo thời gian (TimelineBar truyền xuống đúng thứ tự đang vẽ
 * trên trục, nên tour luôn khớp với cái người dùng nhìn thấy).
 *
 * Tay luôn thắng máy: user click marker/mốc khác giữa chừng -> tour dừng.
 */
export function useEventTour(events: TimelineItem[]): EventTour {
  const playing = useChatUiStore((s) => s.tourPlaying);
  const setTourPlaying = useChatUiStore((s) => s.setTourPlaying);
  const setSelectedEvent = useChatUiStore((s) => s.setSelectedEvent);

  const [index, setIndex] = useState(0);
  /** Id do CHÍNH tour vừa set — mọi giá trị khác nghĩa là user vừa can thiệp. */
  const selfSetRef = useRef<string | null>(null);

  const start = useCallback(() => {
    if (events.length === 0) return;
    setIndex(0);
    setTourPlaying(true);
  }, [events.length, setTourPlaying]);

  const stop = useCallback(() => setTourPlaying(false), [setTourPlaying]);

  // Câu trả lời mới (danh sách sự kiện đổi) -> tour cũ hết nghĩa.
  useEffect(() => {
    setIndex(0);
    setTourPlaying(false);
  }, [events, setTourPlaying]);

  // Bước hiện tại: chiếu sự kiện `index`, hẹn giờ sang sự kiện kế.
  useEffect(() => {
    if (!playing) return;
    const event = events[index];
    if (!event) {
      setTourPlaying(false);
      return;
    }
    selfSetRef.current = event.event_id;
    setSelectedEvent(event.event_id);

    const isLast = index === events.length - 1;
    const timer = window.setTimeout(() => {
      if (isLast) {
        // Kể xong -> bỏ chọn: popover đóng, thanh thời gian về trạng thái không chọn.
        selfSetRef.current = null;
        setSelectedEvent(null);
        setTourPlaying(false);
      } else {
        setIndex((i) => i + 1);
      }
    }, TOUR_STEP_MS);
    return () => window.clearTimeout(timer);
  }, [playing, index, events, setSelectedEvent, setTourPlaying]);

  // User tự chọn sự kiện khác giữa chừng -> dừng tour. Nghe THẲNG store (không qua
  // state của render hiện tại) để không nhầm chính cú set của tour là "user can thiệp".
  useEffect(() => {
    if (!playing) return;
    return useChatUiStore.subscribe((state, prev) => {
      if (state.selectedEventId === prev.selectedEventId) return;
      if (state.selectedEventId !== selfSetRef.current) setTourPlaying(false);
    });
  }, [playing, setTourPlaying]);

  // Rời khung timeline (đổi bố cục, hết sự kiện) -> không để cờ tour treo trong store.
  useEffect(() => () => useChatUiStore.getState().setTourPlaying(false), []);

  return {
    playing,
    currentEvent: playing ? (events[index] ?? null) : null,
    start,
    stop,
  };
}
