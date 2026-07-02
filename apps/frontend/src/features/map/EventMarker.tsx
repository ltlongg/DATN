import { AdvancedMarker, Pin } from "@vis.gl/react-google-maps";
import type { MapMarker } from "@/types";

// Đậm/nhạt theo confidence (explicit vs inferred) — marker.confidence đã là YẾU NHẤT giữa
// event và toạ độ (builder.py).
const PIN_COLORS: Record<string, { background: string; border: string }> = {
  cao: { background: "#A4161A", border: "#7d1013" },
  vừa: { background: "#c4494c", border: "#A4161A" },
  thấp: { background: "#e0a3a4", border: "#c4494c" },
};

export function EventMarker({
  marker,
  selected,
  onSelect,
}: {
  marker: MapMarker;
  selected: boolean;
  onSelect: () => void;
}) {
  const color = PIN_COLORS[marker.confidence] ?? PIN_COLORS["vừa"];
  return (
    <AdvancedMarker
      position={{ lat: marker.lat, lng: marker.lon }}
      title={marker.label}
      onClick={onSelect}
    >
      <Pin
        background={color.background}
        borderColor={color.border}
        glyphColor="#fff"
        scale={selected ? 1.3 : 1}
      />
    </AdvancedMarker>
  );
}
