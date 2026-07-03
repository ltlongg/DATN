import { useEffect, useRef, useState } from "react";
import ForceGraph2D from "react-force-graph-2d";
import type { EntityDetail } from "@/types/kb";

interface GraphNode {
  id: string;
  name: string;
  center: boolean;
}
interface GraphLink {
  source: string;
  target: string;
  keyword: string;
}

/** Đo bề rộng container (guard môi trường không có ResizeObserver — vd jsdom). */
function useWidth() {
  const ref = useRef<HTMLDivElement>(null);
  const [w, setW] = useState(560);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver((entries) => setW(entries[0].contentRect.width));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return { ref, width: w };
}

function buildGraph(detail: EntityDetail): { nodes: GraphNode[]; links: GraphLink[] } {
  const nodes: GraphNode[] = [
    { id: detail.norm_name, name: detail.name, center: true },
  ];
  for (const n of detail.neighbors) {
    if (n.norm_name) nodes.push({ id: n.norm_name, name: n.name ?? n.norm_name, center: false });
  }
  const links: GraphLink[] = [];
  for (const e of detail.edges) {
    if (e.source_norm && e.target_norm) {
      links.push({ source: e.source_norm, target: e.target_norm, keyword: e.keyword ?? "" });
    }
  }
  return { nodes, links };
}

/** Ego-graph 1-hop: node trung tâm + neighbor, cạnh gắn keyword. Click node -> mở entity đó. */
export function EgoGraph({
  detail,
  onSelectEntity,
}: {
  detail: EntityDetail;
  onSelectEntity: (normName: string) => void;
}) {
  const { ref, width } = useWidth();
  const graph = buildGraph(detail);

  if (graph.nodes.length <= 1) {
    return (
      <div className="rounded-lg border border-dashed border-paper-border p-6 text-center text-sm text-ink-soft">
        Không có quan hệ 1-hop cho thực thể này.
      </div>
    );
  }

  return (
    <div ref={ref} className="overflow-hidden rounded-lg border border-paper-border bg-white">
      <ForceGraph2D
        graphData={graph}
        width={width}
        height={320}
        nodeLabel="name"
        nodeRelSize={5}
        linkLabel="keyword"
        linkColor={() => "#c9bda8"}
        onNodeClick={(n) => onSelectEntity((n as GraphNode).id)}
        cooldownTicks={60}
        nodeCanvasObject={(node, ctx, globalScale) => {
          const n = node as GraphNode & { x?: number; y?: number };
          if (n.x == null || n.y == null) return;
          const r = n.center ? 6 : 4;
          ctx.beginPath();
          ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
          ctx.fillStyle = n.center ? "#A4161A" : "#c4494c";
          ctx.fill();

          const fontSize = 12 / globalScale;
          ctx.font = `${n.center ? 700 : 400} ${fontSize}px sans-serif`;
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          const label = n.name;
          const tw = ctx.measureText(label).width;
          const pad = 2 / globalScale;
          ctx.fillStyle = "rgba(255,255,255,0.78)";
          ctx.fillRect(n.x - tw / 2 - pad, n.y + r + pad, tw + pad * 2, fontSize + pad);
          ctx.fillStyle = "#3a332b";
          ctx.fillText(label, n.x, n.y + r + pad * 1.5);
        }}
        nodePointerAreaPaint={(node, color, ctx) => {
          const n = node as GraphNode & { x?: number; y?: number };
          if (n.x == null || n.y == null) return;
          ctx.beginPath();
          ctx.arc(n.x, n.y, n.center ? 6 : 4, 0, 2 * Math.PI);
          ctx.fillStyle = color;
          ctx.fill();
        }}
      />
    </div>
  );
}
