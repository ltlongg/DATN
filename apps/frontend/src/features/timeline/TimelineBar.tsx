import { useEffect, useMemo, useRef, useState } from "react";
import { ConfidenceBadge } from "@/components/ConfidenceBadge";
import { useChatUiStore } from "@/store/chatUiStore";
import type { TimelineItem } from "@/types";

/**
 * Thanh timeline NGANG full-width dưới khung chat (tham khảo time-horizon.pages.dev).
 * Trên trục chỉ có icon + thời gian; click icon mới mở popover chi tiết. Sự kiện sát
 * nhau gom thành cluster (icon số đếm -> popover danh sách); LĂN CHUỘT phóng to tại vị
 * trí con trỏ để tách cluster, KÉO để di chuyển, double-click / nút "Toàn cảnh" reset.
 * Liên kết 2 chiều với map qua `selectedEventId`.
 */

// --- time helpers (time_start dạng "YYYY" | "YYYY-MM" | "YYYY-MM-DD") ---

function parseYearFrac(t: string | null | undefined): number | null {
  if (!t) return null;
  const m = /^(\d{3,4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?/.exec(t.trim());
  if (!m) return null;
  const year = Number(m[1]);
  const month = m[2] ? Number(m[2]) : 1;
  const day = m[3] ? Number(m[3]) : 1;
  return year + (month - 1) / 12 + (day - 1) / 365;
}

/** "1954-05-07" -> "07/05/1954", "1954-05" -> "05/1954", "1954" -> "1954". */
function shortTime(t: string): string {
  const m = /^(\d{3,4})(?:-(\d{1,2}))?(?:-(\d{1,2}))?/.exec(t.trim());
  if (!m) return t;
  if (m[3]) return `${m[3].padStart(2, "0")}/${m[2]!.padStart(2, "0")}/${m[1]}`;
  if (m[2]) return `${m[2].padStart(2, "0")}/${m[1]}`;
  return m[1];
}

function rangeLabel(item: TimelineItem): string {
  if (item.time_end && item.time_end !== item.time_start) {
    return `${shortTime(item.time_start)} – ${shortTime(item.time_end)}`;
  }
  return shortTime(item.time_start);
}

function yearOf(t: string): string {
  return /^(\d{3,4})/.exec(t.trim())?.[1] ?? t;
}

// --- scale + cluster ---

interface Placed {
  item: TimelineItem;
  frac: number; // năm dạng thập phân (1954.35...)
  endFrac: number | null;
}

interface Cluster {
  key: string;
  pct: number; // vị trí % trên trục (theo domain đang zoom)
  placed: Placed[];
}

interface Domain {
  lo: number;
  hi: number;
}

/** Bước tick "đẹp" sao cho có ~5-9 mốc năm trên trục (zoom sâu -> theo tháng). */
function tickStep(span: number): number {
  for (const s of [1 / 12, 0.25, 0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 500]) {
    if (span / s <= 8) return s;
  }
  return 1000;
}

/** Nhãn tick: bước < 1 năm -> "MM/YYYY", còn lại -> năm. */
function tickLabel(y: number, step: number): string {
  if (step >= 1) return String(Math.round(y));
  const year = Math.floor(y + 1e-6);
  const month = Math.round((y - year) * 12) + 1;
  return `${String(month).padStart(2, "0")}/${year}`;
}

const CLUSTER_GAP_PCT = 3.2; // icon cách nhau dưới ngưỡng này -> gom cluster
const MIN_SPAN = 1 / 6; // zoom sâu nhất: 2 tháng

function parsePlaced(items: TimelineItem[]): Placed[] {
  return items
    .map((item) => ({
      item,
      frac: parseYearFrac(item.time_start),
      endFrac: parseYearFrac(item.time_end),
    }))
    .filter((p): p is Placed => p.frac !== null)
    .sort((a, b) => a.frac - b.frac);
}

/** Domain "toàn cảnh": phủ mọi event + đệm 2 biên. */
function fitDomain(placed: Placed[]): Domain {
  const fracs = placed.flatMap((p) => (p.endFrac !== null ? [p.frac, p.endFrac] : [p.frac]));
  const rawLo = Math.min(...fracs);
  const rawHi = Math.max(...fracs);
  const pad = Math.max(1, (rawHi - rawLo) * 0.07);
  return { lo: rawLo - pad, hi: rawHi + pad };
}

function layout(placed: Placed[], domain: Domain) {
  const toPct = (f: number) => ((f - domain.lo) / (domain.hi - domain.lo)) * 100;

  const step = tickStep(domain.hi - domain.lo);
  const ticks: number[] = [];
  for (
    let y = Math.ceil(domain.lo / step - 1e-6) * step;
    y <= domain.hi + 1e-6;
    y += step
  ) {
    ticks.push(y);
  }

  const clusters: Cluster[] = [];
  for (const p of placed) {
    const last = clusters[clusters.length - 1];
    if (last && toPct(p.frac) - toPct(last.placed[last.placed.length - 1].frac) < CLUSTER_GAP_PCT) {
      last.placed.push(p);
    } else {
      clusters.push({ key: p.item.event_id, pct: 0, placed: [p] });
    }
  }
  for (const c of clusters) {
    c.pct = c.placed.reduce((sum, p) => sum + toPct(p.frac), 0) / c.placed.length;
  }
  // chỉ render phần nằm trong khung nhìn (đang zoom/pan)
  return { clusters: clusters.filter((c) => c.pct >= -1 && c.pct <= 101), ticks, toPct };
}

/** Nhãn thời gian ngắn hiện trên icon: 1 sự kiện -> thời điểm; cluster -> khoảng năm. */
function clusterTimeLabel(c: Cluster): string {
  if (c.placed.length === 1) return shortTime(c.placed[0].item.time_start);
  const first = yearOf(c.placed[0].item.time_start);
  const last = yearOf(c.placed[c.placed.length - 1].item.time_start);
  return first === last ? first : `${first}–${last}`;
}

/** Marker đậm/nhạt theo confidence (visualization contract). */
function confidenceOpacity(confidence: string): string {
  if (confidence === "thấp") return "opacity-60";
  if (confidence === "vừa") return "opacity-80";
  return "";
}

// popover rộng w-80 (320px) -> clamp lề 168px để không tràn khỏi màn hình
const POPOVER_LEFT = (pct: number) => ({
  left: `clamp(168px, ${pct}%, calc(100% - 168px))`,
});

export function TimelineBar({ items }: { items: TimelineItem[] }) {
  const selectedEventId = useChatUiStore((s) => s.selectedEventId);
  const setSelected = useChatUiStore((s) => s.setSelectedEvent);
  const [collapsed, setCollapsed] = useState(false);
  const [openCluster, setOpenCluster] = useState<string | null>(null);
  const [view, setView] = useState<Domain | null>(null); // null = toàn cảnh
  const axisRef = useRef<HTMLDivElement | null>(null);
  const dragRef = useRef<{ startX: number; domain: Domain } | null>(null);

  const placed = useMemo(() => parsePlaced(items), [items]);
  const base = useMemo(
    () => (placed.length > 0 ? fitDomain(placed) : null),
    [placed],
  );
  const domain = view ?? base;
  const { clusters, ticks, toPct } = useMemo(
    () => (domain ? layout(placed, domain) : { clusters: [], ticks: [], toPct: () => 0 }),
    [placed, domain],
  );

  // Zoom bằng wheel tại vị trí con trỏ. addEventListener tay vì cần passive:false
  // (React onWheel là passive -> không preventDefault được, trang sẽ cuộn theo).
  useEffect(() => {
    const el = axisRef.current;
    if (!el || !domain || !base) return;
    function onWheel(e: WheelEvent) {
      e.preventDefault();
      const d = domain as Domain;
      const b = base as Domain;
      const rect = (el as HTMLDivElement).getBoundingClientRect();
      const anchor = d.lo + ((e.clientX - rect.left) / rect.width) * (d.hi - d.lo);
      const factor = e.deltaY > 0 ? 1.3 : 1 / 1.3;
      let span = (d.hi - d.lo) * factor;
      span = Math.max(MIN_SPAN, Math.min(span, b.hi - b.lo));
      const ratio = (anchor - d.lo) / (d.hi - d.lo);
      let lo = anchor - span * ratio;
      lo = Math.max(b.lo, Math.min(lo, b.hi - span));
      const next = { lo, hi: lo + span };
      // hết cỡ toàn cảnh -> về trạng thái fit (ẩn nút reset)
      setView(next.hi - next.lo >= b.hi - b.lo - 1e-9 ? null : next);
    }
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [domain, base]);

  // Escape đóng mọi popover.
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        setOpenCluster(null);
        setSelected(null);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setSelected]);

  if (!domain || !base || clusters.length === 0) return null;

  const selectedPlaced =
    selectedEventId === null
      ? null
      : (clusters
          .flatMap((c) => c.placed.map((p) => ({ cluster: c, placed: p })))
          .find((x) => x.placed.item.event_id === selectedEventId) ?? null);
  const listCluster = openCluster ? (clusters.find((c) => c.key === openCluster) ?? null) : null;

  function onClickCluster(c: Cluster) {
    if (c.placed.length === 1) {
      const id = c.placed[0].item.event_id;
      setOpenCluster(null);
      setSelected(id === selectedEventId ? null : id);
    } else {
      setSelected(null);
      setOpenCluster(openCluster === c.key ? null : c.key);
    }
  }

  // Pan bằng kéo chuột trên nền trục (không bắt đầu từ marker để click vẫn ăn).
  function onPointerDown(e: React.PointerEvent<HTMLDivElement>) {
    if (!domain || (e.target as HTMLElement).closest("button")) return;
    dragRef.current = { startX: e.clientX, domain };
    (e.currentTarget as HTMLDivElement).setPointerCapture(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent<HTMLDivElement>) {
    const drag = dragRef.current;
    const el = axisRef.current;
    if (!drag || !el || !base) return;
    const span = drag.domain.hi - drag.domain.lo;
    const dYears = ((e.clientX - drag.startX) / el.getBoundingClientRect().width) * span;
    let lo = drag.domain.lo - dYears;
    lo = Math.max(base.lo, Math.min(lo, base.hi - span));
    const next = { lo, hi: lo + span };
    setView(next.hi - next.lo >= base.hi - base.lo - 1e-9 ? null : next);
  }
  function onPointerUp() {
    dragRef.current = null;
  }

  return (
    <div className="relative border-t border-paper-border bg-paper-card">
      {/* header */}
      <div className="flex items-center justify-between px-4 py-1.5">
        <div className="flex items-center gap-2">
          <span className="inline-block h-2.5 w-2.5 rounded-sm bg-brand" aria-hidden />
          <span className="text-xs font-semibold uppercase tracking-widest text-brand">
            Dòng thời gian
          </span>
          <span className="text-xs text-ink-soft">{items.length} mốc</span>
          <span className="hidden text-[10px] text-ink-soft/70 sm:inline">
            · lăn chuột: phóng to · kéo: di chuyển
          </span>
        </div>
        <div className="flex items-center gap-3">
          {view !== null && (
            <button
              onClick={() => setView(null)}
              className="text-xs font-medium text-brand hover:text-brand-dark"
            >
              ⟲ Toàn cảnh
            </button>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="text-xs text-ink-soft hover:text-brand"
            aria-expanded={!collapsed}
          >
            {collapsed ? "Mở rộng ▴" : "Thu gọn ▾"}
          </button>
        </div>
      </div>

      {!collapsed && (
        <div className="relative mx-5">
          <div
            ref={axisRef}
            className={`relative h-[80px] touch-none select-none ${
              dragRef.current ? "cursor-grabbing" : "cursor-grab"
            }`}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            onDoubleClick={() => setView(null)}
          >
            {/* trục */}
            <div className="absolute left-0 right-0 top-[38px] h-px bg-paper-border" />

            {/* khoảng thời gian (event có time_end) */}
            {clusters.flatMap((c) =>
              c.placed
                .filter((p) => p.endFrac !== null && p.endFrac > p.frac)
                .map((p) => {
                  const left = Math.max(0, toPct(p.frac));
                  const right = Math.min(100, toPct(p.endFrac as number));
                  if (right <= 0 || left >= 100) return null;
                  return (
                    <div
                      key={`span-${p.item.event_id}`}
                      className={`absolute top-[37px] h-[3px] rounded-full ${
                        p.item.event_id === selectedEventId ? "bg-brand/60" : "bg-brand/25"
                      }`}
                      style={{ left: `${left}%`, width: `${Math.max(0.4, right - left)}%` }}
                    />
                  );
                }),
            )}

            {/* tick năm/tháng */}
            {ticks.map((y) => {
              const pct = toPct(y);
              if (pct < 0 || pct > 100) return null;
              const step = tickStep(domain.hi - domain.lo);
              return (
                <div
                  key={`tick-${y.toFixed(3)}`}
                  className="absolute top-[38px] -translate-x-1/2"
                  style={{ left: `${pct}%` }}
                >
                  <div className="mx-auto h-2.5 w-px bg-ink-soft/40" />
                  <div className="mt-0.5 text-center text-[11px] tabular-nums text-ink-soft">
                    {tickLabel(y, step)}
                  </div>
                </div>
              );
            })}

            {/* markers */}
            {clusters.map((c) => {
              const isSelected = c.placed.some((p) => p.item.event_id === selectedEventId);
              const isOpen = openCluster === c.key;
              const single = c.placed.length === 1 ? c.placed[0].item : null;
              return (
                <div
                  key={c.key}
                  className="absolute top-0 -translate-x-1/2 text-center"
                  style={{ left: `${c.pct}%` }}
                >
                  <div
                    className={`whitespace-nowrap text-xs font-medium tabular-nums ${
                      isSelected || isOpen ? "text-brand" : "text-ink-soft"
                    }`}
                  >
                    {clusterTimeLabel(c)}
                  </div>
                  <button
                    onClick={() => onClickCluster(c)}
                    title={single ? single.label : `${c.placed.length} sự kiện — click để xem`}
                    aria-pressed={isSelected || isOpen}
                    className={`mt-1 flex h-9 w-9 items-center justify-center rounded-full border-2 shadow-sm transition ${
                      isSelected || isOpen
                        ? "border-brand bg-brand text-brand-fg ring-2 ring-brand/25"
                        : "border-brand bg-paper-card text-brand hover:bg-brand/10"
                    } ${single ? confidenceOpacity(single.confidence) : ""}`}
                  >
                    {single ? (
                      <span className="block h-2.5 w-2.5 rounded-full bg-current" aria-hidden />
                    ) : (
                      <span className="text-xs font-semibold">
                        {c.placed.length > 99 ? "99+" : c.placed.length}
                      </span>
                    )}
                  </button>
                </div>
              );
            })}
          </div>

          {/* popover danh sách cluster */}
          {listCluster && (
            <div
              className="absolute bottom-[calc(100%+2px)] z-30 w-80 -translate-x-1/2 rounded-lg border border-paper-border bg-paper-card p-2 shadow-lg"
              style={POPOVER_LEFT(listCluster.pct)}
            >
              <div className="flex items-center justify-between px-1 pb-1">
                <span className="text-xs font-medium text-ink-soft">
                  {listCluster.placed.length} sự kiện — lăn chuột trên trục để tách nhỏ
                </span>
                <button
                  onClick={() => setOpenCluster(null)}
                  className="text-xs text-ink-soft hover:text-brand"
                  aria-label="Đóng"
                >
                  ✕
                </button>
              </div>
              <ul className="max-h-48 space-y-1 overflow-y-auto">
                {listCluster.placed.map((p) => (
                  <li key={p.item.event_id}>
                    <button
                      onClick={() => {
                        setOpenCluster(null);
                        setSelected(p.item.event_id);
                      }}
                      className="w-full rounded-md px-2 py-1 text-left text-xs hover:bg-brand/10"
                    >
                      <span className="font-medium tabular-nums text-brand">
                        {rangeLabel(p.item)}
                      </span>{" "}
                      <span className="text-ink">{p.item.label}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* popover chi tiết sự kiện đang chọn */}
          {!listCluster && selectedPlaced && (
            <div
              className="absolute bottom-[calc(100%+2px)] z-30 w-80 -translate-x-1/2 rounded-lg border border-paper-border bg-paper-card p-3 shadow-lg"
              style={POPOVER_LEFT(selectedPlaced.cluster.pct)}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="text-xs font-semibold tabular-nums text-brand">
                  {rangeLabel(selectedPlaced.placed.item)}
                </span>
                <button
                  onClick={() => setSelected(null)}
                  className="text-xs text-ink-soft hover:text-brand"
                  aria-label="Đóng"
                >
                  ✕
                </button>
              </div>
              <p className="mt-1 font-serif text-sm font-semibold text-ink">
                {selectedPlaced.placed.item.label}
              </p>
              <p className="mt-1 line-clamp-4 text-xs text-ink-soft">
                {selectedPlaced.placed.item.summary}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <ConfidenceBadge confidence={selectedPlaced.placed.item.confidence} />
                {selectedPlaced.placed.item.locations.length > 0 && (
                  <span className="text-xs text-ink-soft">
                    {selectedPlaced.placed.item.located && (
                      <span className="text-brand" title="Có toạ độ trên bản đồ">
                        ●{" "}
                      </span>
                    )}
                    {selectedPlaced.placed.item.locations.join(" · ")}
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
