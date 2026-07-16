import { useCallback, useEffect, useRef } from "react";
import { APIProvider, Map, useMap } from "@vis.gl/react-google-maps";
import { EventMarker } from "@/features/map/EventMarker";
import { MapEmptyState } from "@/features/map/MapEmptyState";
import { useChatUiStore } from "@/store/chatUiStore";
import type { MapMarker } from "@/types";

/** Khung nhìn mặc định: trọn Việt Nam, lệch tây để đất liền không bị card chat (float) che. */
const VN_CENTER = { lat: 16.2, lng: 104.5 };
const VN_ZOOM = 5.8; // Map ID vector -> dùng được zoom lẻ

/**
 * Map ID thật trên Cloud Console (vector; style ẨN ĐƯỜNG gắn ở đó, không style JSON
 * trong code — plan §2.1). Thiếu env vẫn cần MỘT mapId vì AdvancedMarker bắt buộc:
 * fallback chuỗi placeholder -> map chạy style mặc định (có đường xá), không vỡ.
 */
const MAP_ID = import.meta.env.VITE_GOOGLE_MAPS_MAP_ID ?? "history-vn";

/** Mức zoom "dí" vào điểm đang kể khi trình chiếu (đủ gần để thấy vùng, chưa tới mức phố). */
const TOUR_FOCUS_ZOOM = 9;

/**
 * Camera phản ứng theo DỮ LIỆU, không theo UI gọi nó (tour engine không cần chạm map):
 * - câu trả lời mới có marker -> đưa khung nhìn về cụm marker; danh sách không đổi ->
 *   đứng yên, không giật map vô cớ;
 * - có sự kiện được chọn -> trượt tới marker của nó; ĐANG TRÌNH CHIẾU thì dí sát vào
 *   (user tự click thì chỉ trượt, tôn trọng mức zoom họ đang xem);
 * - bỏ chọn (kể xong / Escape) -> trả về toàn cảnh.
 * Tách component con vì useMap() chỉ dùng được bên trong <APIProvider>.
 */
function CameraController({
  markers,
  boundsPadding,
}: {
  markers: MapMarker[];
  boundsPadding: number | google.maps.Padding;
}) {
  const map = useMap();
  const selectedEventId = useChatUiStore((s) => s.selectedEventId);
  const tourPlaying = useChatUiStore((s) => s.tourPlaying);
  const lastSignature = useRef<string | null>(null);

  const fitAllMarkers = useCallback(() => {
    if (!map || markers.length === 0) return;
    const bounds = new google.maps.LatLngBounds();
    for (const m of markers) bounds.extend({ lat: m.lat, lng: m.lon });
    map.fitBounds(bounds, boundsPadding);
  }, [map, markers, boundsPadding]);

  useEffect(() => {
    const signature = markers.map((m) => `${m.event_id}-${m.location}`).join("|");
    if (signature === lastSignature.current) return;
    lastSignature.current = signature;
    fitAllMarkers();
  }, [markers, fitAllMarkers]);

  useEffect(() => {
    if (!map) return;
    if (selectedEventId === null) {
      fitAllMarkers();
      return;
    }
    const marker = markers.find((m) => m.event_id === selectedEventId);
    if (!marker) return; // sự kiện không có toạ độ -> chỉ timeline highlight, map đứng yên
    map.panTo({ lat: marker.lat, lng: marker.lon });
    if (tourPlaying && (map.getZoom() ?? 0) < TOUR_FOCUS_ZOOM) map.setZoom(TOUR_FOCUS_ZOOM);
  }, [map, markers, selectedEventId, tourPlaying, fitAllMarkers]);

  return null;
}

/**
 * Bản đồ sự kiện — luôn render base map khi có API key, kể cả 0 marker (map-first:
 * map là NỀN của trang, base map trống là trạng thái hợp lệ). Thiếu key -> empty-state.
 * language/region "vi"/"VN" BẮT BUỘC: label "quần đảo Hoàng Sa/Trường Sa/Biển Đông"
 * thay vì tên tiếng Anh (plan §2.1b).
 */
export function EventMap({
  markers,
  boundsPadding = 48,
}: {
  markers: MapMarker[];
  /** Chừa lề khi fitBounds — layout float truyền lề trái lớn để marker không nằm dưới card chat. */
  boundsPadding?: number | google.maps.Padding;
}) {
  const selectedEventId = useChatUiStore((s) => s.selectedEventId);
  const setSelected = useChatUiStore((s) => s.setSelectedEvent);
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

  if (!apiKey) return <MapEmptyState />;

  return (
    <APIProvider apiKey={apiKey} language="vi" region="VN">
      <Map
        defaultCenter={VN_CENTER}
        defaultZoom={VN_ZOOM}
        mapId={MAP_ID}
        className="h-full w-full"
        gestureHandling="greedy"
        disableDefaultUI
        zoomControl
      >
        {markers.map((m) => (
          <EventMarker
            key={`${m.event_id}-${m.location}`}
            marker={m}
            selected={m.event_id === selectedEventId}
            onSelect={() => setSelected(m.event_id)}
          />
        ))}
        <CameraController markers={markers} boundsPadding={boundsPadding} />
      </Map>
    </APIProvider>
  );
}
