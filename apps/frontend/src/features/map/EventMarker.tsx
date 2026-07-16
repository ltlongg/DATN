import { AdvancedMarker, Pin } from "@vis.gl/react-google-maps";
import type { MapMarker } from "@/types";

/** Viền halo kem (= token paper-card) tách pin khỏi nền terrain xanh của map và
 * buộc marker với tông giấy của app (plan §2.1c). */
const PIN_HALO = "#fffdf9";

/** Ruột pin đậm/nhạt theo confidence (explicit vs inferred) — marker.confidence đã là
 * YẾU NHẤT giữa event và toạ độ (builder.py). Mức "thấp" bão hoà hơn #e0a3a4 cũ để
 * không chìm trên nền xanh. */
const PIN_BACKGROUND: Record<string, string> = {
  cao: "#A4161A",
  vừa: "#c4494c",
  thấp: "#d97f83",
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
  const background = PIN_BACKGROUND[marker.confidence] ?? PIN_BACKGROUND["vừa"];
  return (
    <AdvancedMarker
      position={{ lat: marker.lat, lng: marker.lon }}
      title={marker.label}
      onClick={onSelect}
      zIndex={selected ? 10 : undefined}
    >
      <Pin
        background={background}
        borderColor={PIN_HALO}
        glyphColor={PIN_HALO}
        scale={selected ? 1.3 : 1}
      />
    </AdvancedMarker>
  );
}
