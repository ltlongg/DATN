import { APIProvider, Map } from "@vis.gl/react-google-maps";
import { EventMarker } from "@/features/map/EventMarker";
import { MapEmptyState } from "@/features/map/MapEmptyState";
import { useChatUiStore } from "@/store/chatUiStore";
import type { MapMarker } from "@/types";

const VN_CENTER = { lat: 16.0, lng: 107.8 };

/**
 * Bản đồ sự kiện. Không có marker (gazetteer hoãn) hoặc thiếu API key -> empty-state honest.
 * Chỉ nạp Google Maps khi thực sự có marker + key (tránh gọi script vô ích).
 */
export function EventMap({ markers }: { markers: MapMarker[] }) {
  const selectedEventId = useChatUiStore((s) => s.selectedEventId);
  const setSelected = useChatUiStore((s) => s.setSelectedEvent);
  const apiKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;

  if (markers.length === 0) return <MapEmptyState reason="no-markers" />;
  if (!apiKey) return <MapEmptyState reason="no-key" />;

  return (
    <APIProvider apiKey={apiKey}>
      <Map
        defaultCenter={VN_CENTER}
        defaultZoom={5}
        mapId="history-vn"
        className="h-full w-full"
        gestureHandling="greedy"
        disableDefaultUI={false}
      >
        {markers.map((m) => (
          <EventMarker
            key={`${m.event_id}-${m.location}`}
            marker={m}
            selected={m.event_id === selectedEventId}
            onSelect={() => setSelected(m.event_id)}
          />
        ))}
      </Map>
    </APIProvider>
  );
}
