import * as React from "react";
import { makeProjection, type LatLng } from "@/lib/geo";
import { useGoogleMaps } from "@/lib/googleMaps";
import { sampleWaypoints } from "@/lib/roads";
import type { GraphEdge, GraphNode } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 Mapa de la red vial nacional.

 - Con la key del navegador: fondo de **Google Maps** (se ve Guatemala real, con zoom y arrastre)
   y encima las capas del motor: tramos del grafo, rutas, nodos explorados y marcadores.
   Las rutas con `followRoads` se dibujan por la carretera real (Directions), siguiendo
   exactamente los nodos que eligió nuestro algoritmo.
 - Sin key, o si Google falla: el mismo contenido sobre un mapa esquemático propio.
*/

export interface MapPath {
  codes: string[];
  color: string;
  width?: number;
  opacity?: number;
  dashed?: boolean;
  /** Dibujar por la carretera real (solo con Google). Si falla, se usan líneas rectas entre nodos. */
  followRoads?: boolean;
}

export interface MapNodeMark {
  code: string;
  color: string;
  r?: number;
  opacity?: number;
}

export interface MapMarker extends LatLng {
  id: string;
  /** depot: bodega · stop: parada numerada · pick: punto elegido · dot: pedido pendiente */
  kind: "depot" | "stop" | "pick" | "dot";
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
  /** Reemplaza la capa de tramos (p. ej. tráfico por sentido). Se dibuja debajo de los nodos. */
  renderEdges?: (toXY: (p: LatLng) => [number, number]) => React.ReactNode;
  /** Acerca el mapa a estos puntos (p. ej. la ruta). Sin puntos se ve todo el país. */
  fitTo?: LatLng[];
  onPick?: (point: LatLng) => void;
  /** Ocupa todo el alto del contenedor en lugar de mantener la proporción width/height. */
  fill?: boolean;
  className?: string;
  ariaLabel?: string;
  children?: (toXY: (p: LatLng) => [number, number]) => React.ReactNode;
}

type ToXY = (p: LatLng) => [number, number];

export function NetworkMap(props: NetworkMapProps) {
  const google = useGoogleMaps();
  if (google.status === "ready") return <GoogleNetworkMap {...props} />;
  return (
    <div className={cn("relative flex flex-col", props.fill && "h-full")}>
      <SchematicMap {...props} />
      {google.status === "unavailable" ? (
        <p className="absolute left-2 top-2 max-w-[calc(100%-1rem)] rounded-md border border-line bg-surface/95 px-2 py-1 text-[11px] text-ink-2">
          Mapa esquemático · Google Maps no disponible{google.reason ? `: ${google.reason}` : ""}
        </p>
      ) : null}
    </div>
  );
}

/* ───────────────────────── Capas comunes (SVG) ───────────────────────── */

interface LayerOptions {
  onGoogle: boolean;
  roadGeometry?: Map<string, LatLng[]>;
}

function pathKey(codes: string[]) {
  return codes.join(">");
}

function MapLayers({ props, toXY, opts }: { props: NetworkMapProps; toXY: ToXY; opts: LayerOptions }) {
  const { nodes, edges, edgeStyle, paths = [], nodeMarks = [], markers = [], labels = "cabeceras", renderEdges, children } = props;
  const byCode = React.useMemo(() => new Map(nodes.map((n) => [n.code, n])), [nodes]);
  const xy = (code: string) => {
    const node = byCode.get(code);
    return node ? toXY(node) : null;
  };
  // Sobre Google, la red base va más discreta para que se vea el mapa real
  const baseEdge = opts.onGoogle ? { stroke: "#56595f", width: 1.2, opacity: 0.35 } : { stroke: "#d9d9d5", width: 1.4, opacity: 1 };

  return (
    <>
      {/* Tramos de la red (base) */}
      {renderEdges ? renderEdges(toXY) : null}
      <g strokeLinecap="round" display={renderEdges ? "none" : undefined}>
        {edges.map((edge) => {
          const a = xy(edge.from);
          const b = xy(edge.to);
          if (!a || !b) return null;
          const style = edgeStyle?.(edge) ?? baseEdge;
          return (
            <line key={`${edge.from}|${edge.to}`} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]}
              stroke={style.stroke} strokeWidth={style.width} strokeOpacity={style.opacity ?? 1} />
          );
        })}
      </g>

      {/* Nodos */}
      <g>
        {nodes.map((n) => {
          const [x, y] = toXY(n);
          return <circle key={n.code} cx={x} cy={y} r={n.kind === "cabecera" ? 2.6 : 1.8}
            fill={opts.onGoogle ? "#56595f" : "#b9bab5"} fillOpacity={opts.onGoogle ? 0.55 : 1} />;
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
          const road = path.followRoads ? opts.roadGeometry?.get(pathKey(path.codes)) : undefined;
          const points = road ? road.map(toXY) : path.codes.map(xy).filter((p): p is [number, number] => p !== null);
          if (points.length < 2) return null;
          const d = points.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
          return (
            <g key={i}>
              {/* halo blanco para separar la ruta del fondo */}
              <polyline points={d} stroke="#ffffff" strokeWidth={(path.width ?? 4) + 3} strokeOpacity={path.opacity ?? 1} />
              <polyline points={d} stroke={path.color} strokeWidth={path.width ?? 4}
                strokeOpacity={path.opacity ?? 1} strokeDasharray={path.dashed ? "6 5" : undefined} />
            </g>
          );
        })}
      </g>

      {/* Nombres de las cabeceras (Google ya muestra los nombres de los lugares) */}
      {labels === "cabeceras" && !opts.onGoogle ? (
        <g fontSize={10} fill="#6b6f76" fontFamily="var(--font-sans)" style={{ paintOrder: "stroke" }} stroke="#fafaf9" strokeWidth={3}>
          {nodes.filter((n) => n.kind === "cabecera").map((n) => {
            const [x, y] = toXY(n);
            return <text key={n.code} x={x + 5} y={y - 4}>{n.name}</text>;
          })}
        </g>
      ) : null}

      {children?.(toXY)}

      {/* Marcadores: bodega (cuadro), paradas (círculo numerado), punto elegido */}
      <g fontFamily="var(--font-mono)" fontSize={10} fontWeight={600}>
        {markers.map((m) => {
          const [x, y] = toXY(m);
          if (m.kind === "depot") {
            return (
              <g key={m.id}>
                <rect x={x - 8} y={y - 8} width={16} height={16} rx={3} fill="#111113" stroke="#fff" strokeWidth={2} />
                <title>{m.label ?? "Bodega"}</title>
              </g>
            );
          }
          if (m.kind === "dot") {
            return (
              <g key={m.id}>
                <circle cx={x} cy={y} r={5.5} fill="#2f4bd8" stroke="#fff" strokeWidth={2} />
                {m.label ? <title>{m.label}</title> : null}
              </g>
            );
          }
          if (m.kind === "pick") {
            return <circle key={m.id} cx={x} cy={y} r={7} fill="#2f4bd8" stroke="#fff" strokeWidth={2.5} />;
          }
          return (
            <g key={m.id}>
              <circle cx={x} cy={y} r={10} fill="#111113" stroke="#fff" strokeWidth={2} />
              <text x={x} y={y + 3.5} textAnchor="middle" fill="#fff">{m.label}</text>
            </g>
          );
        })}
      </g>
    </>
  );
}

/* ───────────────────────── Mapa esquemático (sin Google) ───────────────────────── */

function SchematicMap(props: NetworkMapProps) {
  const { nodes, width = 640, height = 720, fitTo, onPick, className, ariaLabel = "Mapa esquemático de la red vial de Guatemala" } = props;
  const svgRef = React.useRef<SVGSVGElement>(null);
  const fitKey = fitTo?.map((p) => `${p.lat.toFixed(4)},${p.lng.toFixed(4)}`).join("|") ?? "";
  const projection = React.useMemo(
    () => (fitTo && fitTo.length > 0 ? makeProjection(fitTo, width, height, 64, 0.35) : makeProjection(nodes, width, height, 28)),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [nodes, width, height, fitKey],
  );

  function handleClick(event: React.MouseEvent<SVGSVGElement>) {
    if (!onPick || !svgRef.current) return;
    const matrix = svgRef.current.getScreenCTM();
    if (!matrix) return;
    const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(matrix.inverse());
    onPick(projection.toLatLng(point.x, point.y));
  }

  return (
    <svg
      ref={svgRef}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("h-auto w-full select-none overflow-hidden", props.fill && "min-h-0 flex-1", onPick && "cursor-crosshair", className)}
      role="img"
      aria-label={ariaLabel}
      onClick={handleClick}
    >
      <MapLayers props={props} toXY={projection.toXY} opts={{ onGoogle: false }} />
    </svg>
  );
}

/* ───────────────────────── Google Maps ───────────────────────── */

const GUATEMALA_CENTER = { lat: 15.6, lng: -90.35 };

// Estilo minimalista: sin puntos de interés ni transporte, colores apagados
const MAP_STYLES: google.maps.MapTypeStyle[] = [
  { featureType: "poi", stylers: [{ visibility: "off" }] },
  { featureType: "transit", stylers: [{ visibility: "off" }] },
  { featureType: "road", elementType: "labels.icon", stylers: [{ visibility: "off" }] },
  { elementType: "geometry", stylers: [{ saturation: -55 }] },
  { featureType: "water", elementType: "geometry", stylers: [{ color: "#d6e2ea" }] },
];

function GoogleNetworkMap(props: NetworkMapProps) {
  const { nodes, width = 640, height = 720, fitTo, onPick, fill, className, ariaLabel = "Mapa de la red vial de Guatemala" } = props;
  const divRef = React.useRef<HTMLDivElement>(null);
  const [map, setMap] = React.useState<google.maps.Map | null>(null);
  const [overlay, setOverlay] = React.useState<google.maps.OverlayView | null>(null);
  const [, redraw] = React.useReducer((x: number) => x + 1, 0);

  // Crear el mapa una sola vez
  React.useEffect(() => {
    if (!divRef.current) return;
    const m = new google.maps.Map(divRef.current, {
      center: GUATEMALA_CENTER,
      zoom: 7,
      styles: MAP_STYLES,
      disableDefaultUI: true,
      zoomControl: true,
      fullscreenControl: true,
      clickableIcons: false,
      gestureHandling: "greedy",
    });
    // Un OverlayView vacío solo para obtener la proyección lat/lng → píxeles
    const ov = new google.maps.OverlayView();
    ov.onAdd = () => {};
    ov.onRemove = () => {};
    ov.draw = () => redraw();
    ov.setMap(m);
    const listener = m.addListener("bounds_changed", () => redraw());
    setMap(m);
    setOverlay(ov);
    return () => {
      listener.remove();
      ov.setMap(null);
    };
  }, []);

  // Clic para elegir un punto (p. ej. la ubicación de un pedido)
  React.useEffect(() => {
    if (!map || !onPick) return;
    map.setOptions({ draggableCursor: "crosshair" });
    const l = map.addListener("click", (e: google.maps.MapMouseEvent) => {
      if (e.latLng) onPick({ lat: e.latLng.lat(), lng: e.latLng.lng() });
    });
    return () => {
      l.remove();
      map.setOptions({ draggableCursor: null });
    };
  }, [map, onPick]);

  // Encuadre: la ruta (fitTo) o todo el país
  const fitKey = fitTo?.map((p) => `${p.lat.toFixed(4)},${p.lng.toFixed(4)}`).join("|") ?? `all:${nodes.length}`;
  React.useEffect(() => {
    if (!map) return;
    const points = fitTo && fitTo.length > 0 ? fitTo : nodes;
    if (points.length === 0) return;
    const bounds = new google.maps.LatLngBounds();
    points.forEach((p) => bounds.extend(p));
    map.fitBounds(bounds, 40);
    // Con pocos puntos juntos no acercar de más
    const once = google.maps.event.addListenerOnce(map, "idle", () => {
      if ((map.getZoom() ?? 0) > 13) map.setZoom(13);
    });
    return () => once.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, fitKey]);

  const roadGeometry = useRoadGeometry(map ? props.paths : undefined, nodes);

  const projection = overlay?.getProjection();
  const toXY: ToXY | null = projection
    ? (p) => {
        const pt = projection.fromLatLngToContainerPixel(new google.maps.LatLng(p.lat, p.lng));
        return pt ? [pt.x, pt.y] : [-9999, -9999];
      }
    : null;

  return (
    <div
      className={cn("relative w-full overflow-hidden rounded-lg", fill ? "h-full min-h-[360px]" : undefined, className)}
      style={fill ? undefined : { aspectRatio: `${width} / ${height}` }}
    >
      <div ref={divRef} className="absolute inset-0" role="region" aria-label={ariaLabel} />
      {toXY ? (
        <svg className="pointer-events-none absolute inset-0 size-full select-none" aria-hidden>
          <MapLayers props={props} toXY={toXY} opts={{ onGoogle: true, roadGeometry }} />
        </svg>
      ) : null}
    </div>
  );
}

/* ─────────────── Dibujo por carretera real (Directions) ─────────────── */

// Caché por secuencia de nodos: la misma ruta no se vuelve a pedir a Google
const roadCache = new Map<string, Promise<LatLng[] | null>>();
/*
 El CAMINO (qué nodos se recorren) lo decidió nuestro Dijkstra / A*. Google Directions solo
 dibuja por dónde va la carretera entre esos puntos: pasa por cada nodo, sin reordenar.
 Directions admite máx. 25 intermedios, así que las rutas largas se submuestrean de forma pareja
 (origen y destino siempre se conservan). Si Directions falla, se dibujan líneas rectas.
*/
function requestRoad(points: LatLng[]): Promise<LatLng[] | null> {
  const sampled = sampleWaypoints(points);
  return new google.maps.DirectionsService()
    .route({
      origin: sampled[0],
      destination: sampled[sampled.length - 1],
      waypoints: sampled.slice(1, -1).map((location) => ({ location, stopover: false })),
      optimizeWaypoints: false,
      travelMode: google.maps.TravelMode.DRIVING,
    })
    .then((r) => r.routes[0]?.overview_path.map((ll) => ({ lat: ll.lat(), lng: ll.lng() })) ?? null)
    .catch(() => null);
}

function useRoadGeometry(paths: MapPath[] | undefined, nodes: GraphNode[]): Map<string, LatLng[]> {
  const [geometry, setGeometry] = React.useState<Map<string, LatLng[]>>(new Map());
  const wanted = (paths ?? []).filter((p) => p.followRoads && p.codes.length >= 2);
  const wantedKey = wanted.map((p) => pathKey(p.codes)).join("|");

  React.useEffect(() => {
    if (!wanted.length) return;
    const byCode = new Map(nodes.map((n) => [n.code, n]));
    let alive = true;
    wanted.forEach((path) => {
      const key = pathKey(path.codes);
      const points = path.codes.map((c) => byCode.get(c)).filter((n): n is GraphNode => !!n).map((n) => ({ lat: n.lat, lng: n.lng }));
      if (points.length < 2) return;
      if (!roadCache.has(key)) roadCache.set(key, requestRoad(points));
      roadCache.get(key)!.then((road) => {
        if (alive && road) setGeometry((prev) => (prev.has(key) ? prev : new Map(prev).set(key, road)));
      });
    });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [wantedKey, nodes]);

  return geometry;
}
