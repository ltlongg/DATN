// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TOUR_STEP_MS, useEventTour } from "@/features/timeline/useEventTour";
import { useChatUiStore } from "@/store/chatUiStore";
import type { TimelineItem } from "@/types";

function event(id: string, time: string): TimelineItem {
  return {
    event_id: id,
    label: `sự kiện ${id}`,
    summary: "",
    time_start: time,
    time_end: null,
    confidence: "cao",
    locations: [],
    located: false,
  };
}

const EVENTS = [event("e1", "1858"), event("e2", "1930"), event("e3", "1954")];

const store = () => useChatUiStore.getState();

beforeEach(() => {
  vi.useFakeTimers();
  act(() => {
    store().setSelectedEvent(null);
    store().setTourPlaying(false);
  });
});

afterEach(() => {
  // Hook cũ còn mounted sẽ vẫn nghe store -> tưởng cú set của tour sau là "user can
  // thiệp" và tắt nó. Gỡ hẳn giữa các test (RTL ở repo này không auto-cleanup).
  cleanup();
  vi.useRealTimers();
});

/** Nhảy qua 1 bước trình chiếu. */
function step() {
  act(() => {
    vi.advanceTimersByTime(TOUR_STEP_MS);
  });
}

describe("useEventTour", () => {
  it("chiếu lần lượt từng sự kiện theo đúng thứ tự được truyền vào", () => {
    const { result } = renderHook(() => useEventTour(EVENTS));

    act(() => result.current.start());
    expect(store().selectedEventId).toBe("e1");
    expect(result.current.playing).toBe(true);
    expect(result.current.currentEvent?.event_id).toBe("e1");

    step();
    expect(store().selectedEventId).toBe("e2");

    step();
    expect(store().selectedEventId).toBe("e3");
  });

  it("kể xong sự kiện cuối thì tự dừng và bỏ chọn (camera về toàn cảnh)", () => {
    const { result } = renderHook(() => useEventTour(EVENTS));

    act(() => result.current.start());
    step();
    step();
    expect(store().selectedEventId).toBe("e3");
    expect(store().tourPlaying).toBe(true);

    step(); // hết danh sách
    expect(store().tourPlaying).toBe(false);
    expect(store().selectedEventId).toBeNull();
    expect(result.current.currentEvent).toBeNull();
  });

  it("user tự chọn sự kiện khác giữa chừng -> tour dừng (tay thắng máy)", () => {
    const { result } = renderHook(() => useEventTour(EVENTS));

    act(() => result.current.start());
    step();
    expect(store().selectedEventId).toBe("e2");

    act(() => store().setSelectedEvent("e3")); // user click marker/mốc khác
    expect(store().tourPlaying).toBe(false);
    expect(store().selectedEventId).toBe("e3"); // lựa chọn của user được giữ

    step(); // tour đã dừng -> không tự nhảy tiếp nữa
    expect(store().selectedEventId).toBe("e3");
  });

  it("bỏ chọn (Escape) giữa chừng cũng dừng tour", () => {
    const { result } = renderHook(() => useEventTour(EVENTS));

    act(() => result.current.start());
    act(() => store().setSelectedEvent(null));

    expect(store().tourPlaying).toBe(false);
  });

  it("bấm dừng -> giữ nguyên sự kiện đang xem, không nhảy tiếp", () => {
    const { result } = renderHook(() => useEventTour(EVENTS));

    act(() => result.current.start());
    act(() => result.current.stop());

    expect(store().tourPlaying).toBe(false);
    expect(store().selectedEventId).toBe("e1");

    step();
    expect(store().selectedEventId).toBe("e1");
  });

  it("câu trả lời mới (danh sách sự kiện đổi) -> tour cũ dừng", () => {
    const { result, rerender } = renderHook(({ events }) => useEventTour(events), {
      initialProps: { events: EVENTS },
    });

    act(() => result.current.start());
    expect(store().tourPlaying).toBe(true);

    rerender({ events: [event("x1", "1945")] });
    expect(store().tourPlaying).toBe(false);
  });

  it("chạy lại tour sau khi đã kể xong -> bắt đầu lại từ sự kiện đầu", () => {
    const { result } = renderHook(() => useEventTour(EVENTS));

    act(() => result.current.start());
    step();
    expect(store().selectedEventId).toBe("e2");

    act(() => result.current.stop());
    act(() => result.current.start());
    expect(store().selectedEventId).toBe("e1");
  });

  it("không có sự kiện nào -> start() không làm gì", () => {
    const { result } = renderHook(() => useEventTour([]));

    act(() => result.current.start());

    expect(store().tourPlaying).toBe(false);
    expect(store().selectedEventId).toBeNull();
  });

  it("rời khung timeline -> không để cờ trình chiếu treo lại trong store", () => {
    const { result, unmount } = renderHook(() => useEventTour(EVENTS));

    act(() => result.current.start());
    expect(store().tourPlaying).toBe(true);

    unmount();
    expect(store().tourPlaying).toBe(false);
  });
});
