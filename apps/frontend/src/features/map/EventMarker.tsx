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

/** Đường kính (px) vòng tròn của marker "area". Nhỏ hơn pin có chủ ý: nó là một nơi
 * TIÊU BIỂU được nhắc tên, không phải toạ độ nơi sự kiện xảy ra. */
const AREA_DOT_SIZE = 18;

/** Độ mờ ruột vòng "area", dạng alpha hex ghép sau màu 6 số (0x33 ≈ 20%). */
const AREA_FILL_ALPHA = "33";

/**
 * Vòng tròn RỖNG cho marker `scope="area"`. Khác pin đặc ở đúng cái nó cần nói: sự kiện
 * KHÔNG xảy ra tại điểm này, đây chỉ là một địa danh tiêu biểu của một diễn biến trải
 * rộng (phong trào, địa bàn hoạt động). Vẽ giống pin là khẳng định sai chỗ xảy ra.
 */
function AreaDot({ color, selected }: { color: string; selected: boolean }) {
  return (
    <div className="grid h-9 w-9 cursor-pointer place-items-center" aria-hidden>
      <div
        className="rounded-full border-2 transition-transform"
        style={{
          width: AREA_DOT_SIZE,
          height: AREA_DOT_SIZE,
          borderColor: color,
          backgroundColor: `${color}${AREA_FILL_ALPHA}`,
          boxShadow: `0 0 0 1.5px ${PIN_HALO}`,
          transform: selected ? "scale(1.35)" : undefined,
        }}
      />
    </div>
  );
}

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
      title={`${marker.location}: ${marker.label}`}
      onClick={onSelect}
      zIndex={selected ? 10 : undefined}
    >
      {marker.scope === "area" ? (
        <AreaDot color={background} selected={selected} />
      ) : (
        <Pin
          background={background}
          borderColor={PIN_HALO}
          glyphColor={PIN_HALO}
          scale={selected ? 1.3 : 1}
        />
      )}
    </AdvancedMarker>
  );
}
