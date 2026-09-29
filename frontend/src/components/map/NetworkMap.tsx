import * as React from "react";
import { makeProjection, type LatLng } from "@/lib/geo";
import type { GraphEdge, GraphNode } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 Mapa esquemático de la red vial nacional: nodos y tramos del grafo tal como
 los ve el algoritmo, proyectados desde lat/lon. No depende de Google.
*/

export interface MapPath {
  codes: string[];
  color: string;
  width?: number;
  opacity?: number;
  dashed?: boolean;
}

export interface MapNodeMark {
  code: string;
  color: string;
  r?: number;
  opacity?: number;
}

export interface MapMarker extends LatLng {
  id: string;
  kind: "depot" | "stop" | "pick";
  label?: string;
}

export interface NetworkMapProps {
  nodes: GraphNode[];
  edges: GraphEdge[];
  width?: number;
  height?: number;
  edgeStyle?: (edge: GraphEdge) => { stroke: string; width: number; opacity?: number } | null;
  paths?: MapPath[];
  nodeMarks?: MapNodeMark[];
  markers?: MapMarker[];
  labels?: "cabeceras" | "none";
  /** Acerca el mapa a estos puntos (p. ej. la ruta). Sin puntos se ve todo el país. */
  fitTo?: LatLng[];
  onPick?: (point: LatLng) => void;
  className?: string;
  ariaLabel?: string;
  children?: (toXY: (p: LatLng) => [number, number]) => React.ReactNode;
}

export function NetworkMap({
  nodes,
  edges,
  width = 640,
  height = 720,
  edgeStyle,
  paths = [],
  nodeMarks = [],
  markers = [],
  labels = "cabeceras",
  fitTo,
  onPick,
  className,
  ariaLabel = "Mapa esquemático de la red vial de Guatemala",
  children,
}: NetworkMapProps) {
  const svgRef = React.useRef<SVGSVGElement>(null);
  const fitKey = fitTo?.map((p) => `${p.lat.toFixed(4)},${p.lng.toFixed(4)}`).join("|") ?? "";
  const projection = React.useMemo(
    () => (fitTo && fitTo.length > 0 ? makeProjection(fitTo, width, height, 64, 0.35) : makeProjection(nodes, width, height, 28)),
    [nodes, width, height, fitKey],
  );
  const byCode = React.useMemo(() => new Map(nodes.map((n) => [n.code, n])), [nodes]);
  const xy = (code: string) => {
    const node = byCode.get(code);
    return node ? projection.toXY(node) : null;
  };

  function handleClick(event: React.MouseEvent<SVGSVGElement>) {
    if (!onPick || !svgRef.current) return;
    const svg = svgRef.current;
    const matrix = svg.getScreenCTM();
    if (!matrix) return;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    onPick(projection.toLatLng(point.x, point.y));
  }

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("h-auto w-full select-none overflow-hidden", onPick && "cursor-crosshair", className)}
      role="img"
      aria-label={ariaLabel}
      onClick={handleClick}
    >
      {/* Tramos de la red (base) */}
      <g strokeLinecap="round">
        {edges.map((edge) => {
          const a = xy(edge.from);
          const b = xy(edge.to);
          if (!a || !b) return null;
          const style = edgeStyle?.(edge) ?? { stroke: "#d9d9d5", width: 1.4 };
          return (
            <line key={`${edge.from}|${edge.to}`} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]}
              stroke={style.stroke} strokeWidth={style.width} strokeOpacity={style.opacity ?? 1} />
          );
        })}
      </g>

      {/* Nodos */}
      <g>
        {nodes.map((n) => {
          const [x, y] = projection.toXY(n);
          return <circle key={n.code} cx={x} cy={y} r={n.kind === "cabecera" ? 2.6 : 1.8} fill="#b9bab5" />;
        })}
      </g>

      {/* Nodos resaltados (p. ej. explorados por un algoritmo) */}
      <g>
        {nodeMarks.map((m) => {
          const p = xy(m.code);
          return p ? <circle key={m.code} cx={p[0]} cy={p[1]} r={m.r ?? 5} fill={m.color} fillOpacity={m.opacity ?? 0.35} /> : null;
        })}
      </g>

      {/* Rutas */}
      <g fill="none" strokeLinecap="round" strokeLinejoin="round">
        {paths.map((path, i) => {
          const points = path.codes.map(xy).filter((p): p is [number, number] => p !== null);
          if (points.length < 2) return null;
          return (
            <g key={i}>
              {/* halo blanco para separar la ruta de la red */}
              <polyline points={points.map((p) => p.join(",")).join(" ")} stroke="#ffffff" strokeWidth={(path.width ?? 4) + 3} strokeOpacity={path.opacity ?? 1} />
              <polyline points={points.map((p) => p.join(",")).join(" ")} stroke={path.color} strokeWidth={path.width ?? 4}
                strokeOpacity={path.opacity ?? 1} strokeDasharray={path.dashed ? "6 5" : undefined} />
            </g>
          );
        })}
      </g>

      {/* Nombres de las cabeceras */}
      {labels === "cabeceras" ? (
        <g fontSize={10} fill="#6b6f76" fontFamily="var(--font-sans)" style={{ paintOrder: "stroke" }} stroke="#fafaf9" strokeWidth={3}>
          {nodes.filter((n) => n.kind === "cabecera").map((n) => {
            const [x, y] = projection.toXY(n);
            return <text key={n.code} x={x + 5} y={y - 4}>{n.name}</text>;
          })}
        </g>
      ) : null}

      {children?.(projection.toXY)}

      {/* Marcadores: bodega (cuadro), paradas (círculo numerado), punto elegido */}
      <g fontFamily="var(--font-mono)" fontSize={10} fontWeight={600}>
        {markers.map((m) => {
          const [x, y] = projection.toXY(m);
          if (m.kind === "depot") {
            return (
              <g key={m.id}>
                <rect x={x - 7} y={y - 7} width={14} height={14} rx={3} fill="#111113" stroke="#fff" strokeWidth={2} />
                <title>{m.label ?? "Bodega"}</title>
              </g>
            );
          }
          if (m.kind === "pick") {
            return <circle key={m.id} cx={x} cy={y} r={7} fill="#2f4bd8" stroke="#fff" strokeWidth={2.5} />;
          }
          return (
            <g key={m.id}>
              <circle cx={x} cy={y} r={9} fill="#111113" stroke="#fff" strokeWidth={2} />
              <text x={x} y={y + 3.5} textAnchor="middle" fill="#fff">{m.label}</text>
            </g>
          );
        })}
      </g>
    </svg>
  );
}
