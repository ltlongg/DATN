import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { APIProvider, InfoWindow, Map, useMap } from "@vis.gl/react-google-maps";
import { CalendarDays, MapPin } from "lucide-react";
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

function markerKey(marker: MapMarker): string {
  return `${marker.event_id}-${marker.location}`;
}

function timeLabel(value: string | null | undefined): string {
  if (!value) return "Chưa rõ thời gian";
  const parts = value.split("-");
  if (parts.length === 3) return `${parts[2]}/${parts[1]}/${parts[0]}`;
  if (parts.length === 2) return `${parts[1]}/${parts[0]}`;
  return value;
}

function confidenceLabel(confidence: string): string {
  if (confidence === "cao") return "Độ tin cậy cao";
  if (confidence === "vừa") return "Độ tin cậy vừa";
  return "Độ tin cậy thấp";
}

/** Nội dung gọn trong popup Google Maps; click marker mới mở, không che map hàng loạt. */
function MarkerDetails({ marker }: { marker: MapMarker }) {
  return (
    <article className="w-[min(19rem,calc(100vw-5rem))] py-0.5 pr-1 font-sans text-ink">
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-[11px] font-medium text-brand">
        <span className="flex items-center gap-1">
          <CalendarDays size={13} aria-hidden />
          {timeLabel(marker.time_start)}
        </span>
        <span className="flex items-center gap-1">
          <MapPin size={13} aria-hidden />
          {marker.location}
        </span>
      </div>

      <h3 className="mt-2 font-serif text-sm font-semibold leading-snug text-ink">
        {marker.label}
      </h3>
      {marker.summary && (
        <p className="mt-1.5 max-h-28 overflow-y-auto text-xs leading-relaxed text-ink-soft">
          {marker.summary}
        </p>
      )}

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-paper-border pt-2">
        <span className="rounded-full bg-brand/10 px-2 py-0.5 text-[10px] font-medium text-brand">
          {confidenceLabel(marker.confidence)}
        </span>
        <span className="rounded-full bg-paper px-2 py-0.5 text-[10px] text-ink-soft">
          {marker.scope === "area" ? "Địa bàn diễn biến" : "Điểm xảy ra sự kiện"}
        </span>
      </div>
    </article>
  );
}

function boundsOf(markers: MapMarker[]): google.maps.LatLngBounds {
  const bounds = new google.maps.LatLngBounds();
  for (const m of markers) bounds.extend({ lat: m.lat, lng: m.lon });
  return bounds;
}

/**
 * Camera phản ứng theo DỮ LIỆU, không theo UI gọi nó (tour engine không cần chạm map):
 * - câu trả lời mới có marker -> đưa khung nhìn về cụm marker; danh sách không đổi ->
 *   đứng yên, không giật map vô cớ;
 * - chọn sự kiện MỘT nơi -> trượt tới marker; ĐANG TRÌNH CHIẾU thì dí sát vào (user tự
 *   click thì chỉ trượt, tôn trọng mức zoom họ đang xem);
 * - chọn sự kiện NHIỀU nơi -> khớp khung nhìn quanh cả cụm. Đây là chỗ event `area`
 *   (phong trào trải rộng) hiển thị đúng nghĩa: cái phải nhìn là ĐỊA BÀN, không phải
 *   một điểm được chọn tuỳ tiện vì nó tình cờ đứng đầu mảng. Bounding box ở đây là CHỖ
 *   ĐỂ NHÌN, không phải hình vẽ ra — không khẳng định ranh giới nào cả.
 *   Nhánh này KHÔNG ép TOUR_FOCUS_ZOOM: fitBounds đã tự chọn zoom, ép thêm là phá khung
 *   vừa khớp.
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
    map.fitBounds(boundsOf(markers), boundsPadding);
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
    const own = markers.filter((m) => m.event_id === selectedEventId);
    if (own.length === 0) return; // sự kiện không có toạ độ -> chỉ timeline highlight, map đứng yên
    if (own.length > 1) {
      map.fitBounds(boundsOf(own), boundsPadding);
      return;
    }
    map.panTo({ lat: own[0].lat, lng: own[0].lon });
    if (tourPlaying && (map.getZoom() ?? 0) < TOUR_FOCUS_ZOOM) map.setZoom(TOUR_FOCUS_ZOOM);
  }, [map, markers, selectedEventId, tourPlaying, boundsPadding, fitAllMarkers]);

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
  const [openMarkerKey, setOpenMarkerKey] = useState<string | null>(null);
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

  const openMarker = useMemo(
    () => markers.find((marker) => markerKey(marker) === openMarkerKey) ?? null,
    [markers, openMarkerKey],
  );

  // Timeline/tour chuyển sang event khác hoặc bỏ chọn thì popup cũ không được nằm lại.
  useEffect(() => {
    if (openMarker && openMarker.event_id !== selectedEventId) setOpenMarkerKey(null);
  }, [openMarker, selectedEventId]);

  function selectMarker(marker: MapMarker) {
    const key = markerKey(marker);
    if (key === openMarkerKey) {
      setOpenMarkerKey(null);
      setSelected(null);
      return;
    }
    setOpenMarkerKey(key);
    setSelected(marker.event_id);
  }

  function closeDetails() {
    setOpenMarkerKey(null);
    if (openMarker?.event_id === selectedEventId) setSelected(null);
  }

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
            key={markerKey(m)}
            marker={m}
            selected={m.event_id === selectedEventId}
            onSelect={() => selectMarker(m)}
          />
        ))}
        {openMarker && (
          <InfoWindow
            position={{ lat: openMarker.lat, lng: openMarker.lon }}
            onCloseClick={closeDetails}
            pixelOffset={[0, -38]}
            ariaLabel={`Chi tiết sự kiện: ${openMarker.label}`}
          >
            <MarkerDetails marker={openMarker} />
          </InfoWindow>
        )}
        <CameraController markers={markers} boundsPadding={boundsPadding} />
      </Map>
    </APIProvider>
  );
}
