// @vitest-environment jsdom
import { act, cleanup, fireEvent, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { EventMap } from "@/features/map/EventMap";
import { useChatUiStore } from "@/store/chatUiStore";
import type { MapMarker } from "@/types";

/** Camera giả: ghi lại lệnh nhận được để khẳng định ĐÃ CHỌN ĐÚNG NƯỚC ĐI. */
const cam = {
  fitBounds: vi.fn(),
  panTo: vi.fn(),
  setZoom: vi.fn(),
  getZoom: vi.fn(() => 6),
};

vi.mock("@vis.gl/react-google-maps", () => ({
  APIProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  Map: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  useMap: () => cam,
  AdvancedMarker: ({
    children,
    onClick,
    title,
  }: {
    children: React.ReactNode;
    onClick?: () => void;
    title?: string;
  }) => (
    <button type="button" aria-label={title} onClick={onClick}>
      {children}
    </button>
  ),
  Pin: () => <div data-testid="pin" />,
  InfoWindow: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="info-window">{children}</div>
  ),
}));

/** LatLngBounds tối giản: chỉ cần gom điểm để test đọc lại được cụm đã fit. */
class FakeBounds {
  points: { lat: number; lng: number }[] = [];
  extend(p: { lat: number; lng: number }) {
    this.points.push(p);
    return this;
  }
}

const store = () => useChatUiStore.getState();

function marker(event_id: string, location: string, lat: number, lon: number, scope: MapMarker["scope"]): MapMarker {
  return {
    event_id,
    label: `Sự kiện tại ${location}`,
    summary: `Mô tả diễn biến tại ${location}.`,
    location,
    lat,
    lon,
    confidence: "cao",
    time_start: "1975-04-30",
    scope,
  };
}

// Event "area" 3 nơi + event "sites" 1 nơi.
const AREA = [
  marker("e-area", "Gò Công", 10.36, 106.67, "area"),
  marker("e-area", "Tân An", 10.53, 106.41, "area"),
  marker("e-area", "Mỹ Tho", 10.36, 106.36, "area"),
];
const SITE = marker("e-site", "Đà Nẵng", 16.05, 108.2, "sites");
const MARKERS = [...AREA, SITE];

beforeEach(() => {
  vi.stubEnv("VITE_GOOGLE_MAPS_API_KEY", "test-key");
  (globalThis as unknown as { google: unknown }).google = { maps: { LatLngBounds: FakeBounds } };
  cam.fitBounds.mockClear();
  cam.panTo.mockClear();
  cam.setZoom.mockClear();
  act(() => {
    store().setSelectedEvent(null);
    store().setTourPlaying(false);
  });
});

afterEach(() => {
  cleanup();
  vi.unstubAllEnvs();
});

/** Cụm điểm của lần fitBounds gần nhất. */
function lastFitted(): { lat: number; lng: number }[] {
  const bounds = cam.fitBounds.mock.calls.at(-1)?.[0] as FakeBounds;
  return bounds.points;
}

describe("CameraController", () => {
  it("chọn sự kiện NHIỀU nơi -> khớp khung nhìn quanh cả cụm, không bay tới một điểm", () => {
    render(<EventMap markers={MARKERS} />);
    act(() => store().setSelectedEvent("e-area"));

    expect(cam.panTo).not.toHaveBeenCalled();
    expect(lastFitted()).toEqual([
      { lat: 10.36, lng: 106.67 },
      { lat: 10.53, lng: 106.41 },
      { lat: 10.36, lng: 106.36 },
    ]);
  });

  it("chọn sự kiện MỘT nơi -> trượt tới đúng điểm đó", () => {
    render(<EventMap markers={MARKERS} />);
    act(() => store().setSelectedEvent("e-site"));

    expect(cam.panTo).toHaveBeenCalledWith({ lat: 16.05, lng: 108.2 });
  });

  it("đang trình chiếu: sự kiện một nơi thì dí zoom, sự kiện nhiều nơi thì để fitBounds tự lo", () => {
    act(() => store().setTourPlaying(true));
    render(<EventMap markers={MARKERS} />);

    act(() => store().setSelectedEvent("e-site"));
    expect(cam.setZoom).toHaveBeenCalledWith(9);

    cam.setZoom.mockClear();
    act(() => store().setSelectedEvent("e-area"));
    expect(cam.setZoom).not.toHaveBeenCalled(); // ép zoom sẽ phá khung vừa khớp
  });

  it("sự kiện không có marker nào -> map đứng yên (chỉ timeline highlight)", () => {
    render(<EventMap markers={MARKERS} />);
    cam.fitBounds.mockClear();
    act(() => store().setSelectedEvent("e-khong-toa-do"));

    expect(cam.panTo).not.toHaveBeenCalled();
    expect(cam.fitBounds).not.toHaveBeenCalled();
  });

  it("bỏ chọn -> trả về toàn cảnh mọi marker", () => {
    render(<EventMap markers={MARKERS} />);
    act(() => store().setSelectedEvent("e-site"));
    cam.fitBounds.mockClear();
    act(() => store().setSelectedEvent(null));

    expect(lastFitted()).toHaveLength(MARKERS.length);
  });
});

describe("EventMarker", () => {
  it("chỉ marker 'sites' vẽ pin đặc; 'area' vẽ vòng rỗng", () => {
    const { getAllByTestId, container } = render(<EventMap markers={MARKERS} />);

    expect(getAllByTestId("pin")).toHaveLength(1); // đúng một marker 'sites'
    expect(container.querySelectorAll("div.rounded-full")).toHaveLength(AREA.length);
  });

  it("click marker mở popup chi tiết ngay trên map; click lần nữa đóng popup", () => {
    const { getByLabelText, getByTestId, queryByTestId } = render(<EventMap markers={MARKERS} />);
    const siteMarker = getByLabelText("Đà Nẵng: Sự kiện tại Đà Nẵng");

    fireEvent.click(siteMarker);
    expect(getByTestId("info-window").textContent).toContain("30/04/1975");
    expect(getByTestId("info-window").textContent).toContain("Sự kiện tại Đà Nẵng");
    expect(getByTestId("info-window").textContent).toContain("Mô tả diễn biến tại Đà Nẵng.");
    expect(store().selectedEventId).toBe("e-site");

    fireEvent.click(siteMarker);
    expect(queryByTestId("info-window")).toBeNull();
    expect(store().selectedEventId).toBeNull();
  });
});
