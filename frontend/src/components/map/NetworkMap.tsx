import { motion, useReducedMotion } from "motion/react";
import * as React from "react";
import { makeProjection, type LatLng } from "@/lib/geo";
import { useGoogleMaps } from "@/lib/googleMaps";
import { cascadeDelay, mapStyles } from "@/lib/mapTheme";
import { sampleWaypoints } from "@/lib/roads";
import { useTheme } from "@/lib/theme";
import type { GraphEdge, GraphNode } from "@/lib/types";
import { cn } from "@/lib/utils";
import { pickMarker } from "./markerPick";

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
  /** Ruta "en camino": un destello discontinuo la recorre despacio. */
  flow?: boolean;
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

// Animaciones CSS ligeras (sin un spring por elemento). Los retardos van en --d.
const MAP_CSS = `
@keyframes nm-fade { from { opacity: 0 } }
@keyframes nm-pop { from { opacity: 0; transform: scale(.4) } }
@keyframes nm-flow { to { stroke-dashoffset: -24 } }
.nm-fade { animation: nm-fade .28s ease-out both; animation-delay: var(--d, 0s) }
.nm-pop { animation: nm-pop .34s cubic-bezier(.22,1,.36,1) both; animation-delay: var(--d, 0s); transform-box: fill-box; transform-origin: center }
.nm-flow { animation: nm-flow 1.4s linear infinite }
.nm-marker { outline: none; cursor: pointer }
.nm-marker:focus-visible .nm-ring { opacity: 1 }
`;

// Máximo de elementos que se animan en cascada; el resto aparece de golpe
const MAX_CASCADE = 120;
const DRAW_SECONDS = 1;

function delayStyle(index: number, count: number, total: number): React.CSSProperties {
  return { "--d": `${cascadeDelay(index, count, total).toFixed(3)}s` } as React.CSSProperties;
}

function MapLayers({ props, toXY, opts }: { props: NetworkMapProps; toXY: ToXY; opts: LayerOptions }) {
  const { nodes, edges, edgeStyle, paths = [], nodeMarks = [], markers = [], labels = "cabeceras", renderEdges, children } = props;
  const reduce = useReducedMotion();
  const [tip, setTip] = React.useState<string | null>(null);
  const byCode = React.useMemo(() => new Map(nodes.map((n) => [n.code, n])), [nodes]);
  const xy = (code: string) => {
    const node = byCode.get(code);
    return node ? toXY(node) : null;
  };
  // Sobre Google, la red base va más discreta para que se vea el mapa real
  const baseEdge = opts.onGoogle
    ? { stroke: "var(--color-ink-3)", width: 1.2, opacity: 0.35 }
    : { stroke: "var(--color-line-strong)", width: 1.4, opacity: 1 };
  const markCount = Math.min(nodeMarks.length, MAX_CASCADE);

  return (
    <>
      <style>{MAP_CSS}</style>

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
            fill={opts.onGoogle ? "var(--color-ink-3)" : "var(--color-line-strong)"} fillOpacity={opts.onGoogle ? 0.55 : 1} />;
        })}
      </g>

      {/* Nodos resaltados (p. ej. explorados por un algoritmo): aparecen en el orden recibido */}
      <g>
        {nodeMarks.map((m, i) => {
          const p = xy(m.code);
          if (!p) return null;
          const animated = !reduce && i < MAX_CASCADE;
          return (
            <circle key={m.code} cx={p[0]} cy={p[1]} r={m.r ?? 5} fill={m.color} fillOpacity={m.opacity ?? 0.35}
              className={animated ? "nm-fade" : undefined} style={animated ? delayStyle(i, markCount, 1.2) : undefined} />
          );
        })}
      </g>

      {/* Rutas: se dibujan de origen a destino al aparecer */}
      <g fill="none" strokeLinecap="round" strokeLinejoin="round">
        {paths.map((path, i) => {
          const road = path.followRoads ? opts.roadGeometry?.get(pathKey(path.codes)) : undefined;
          const points = road ? road.map(toXY) : path.codes.map(xy).filter((p): p is [number, number] => p !== null);
          if (points.length < 2) return null;
          const d = points.map((p) => `${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
          const w = path.width ?? 4;
          const opacity = path.opacity ?? 1;
          // pathLength 0→1 no combina con trazos discontinuos: esas rutas aparecen con un fundido
          const draw = !reduce && !path.dashed;
          const fade = !reduce && !!path.dashed;
          const grow = draw
            ? { initial: { pathLength: 0 }, animate: { pathLength: 1 }, transition: { duration: DRAW_SECONDS, ease: [0.22, 1, 0.36, 1] as const } }
            : {};
          return (
            <g key={pathKey(path.codes) || i}>
              {/* halo del color de la superficie para separar la ruta del fondo */}
              <motion.polyline points={d} stroke="var(--color-surface)" strokeWidth={w + 3} strokeOpacity={opacity} {...grow} />
              <motion.polyline points={d} stroke={path.color} strokeWidth={w} strokeOpacity={opacity}
                strokeDasharray={path.dashed ? "6 5" : undefined} className={fade ? "nm-fade" : undefined} {...grow} />
              {path.flow && !reduce ? (
                <polyline points={d} stroke="var(--color-surface)" strokeWidth={Math.max(1.5, w - 2)} strokeOpacity={0.6}
                  strokeDasharray="2 10" className="nm-flow" style={{ animationDelay: `${DRAW_SECONDS}s` }} />
              ) : null}
            </g>
          );
        })}
      </g>

      {/* Nombres de las cabeceras (Google ya muestra los nombres de los lugares) */}
      {labels === "cabeceras" && !opts.onGoogle ? (
        <g fontSize={10} fill="var(--color-ink-2)" fontFamily="var(--font-sans)" style={{ paintOrder: "stroke" }} stroke="var(--color-surface)" strokeWidth={3}>
          {nodes.filter((n) => n.kind === "cabecera").map((n) => {
            const [x, y] = toXY(n);
            return <text key={n.code} x={x + 5} y={y - 4}>{n.name}</text>;
          })}
        </g>
      ) : null}

      {children?.(toXY)}

      {/* Marcadores, distinguibles por forma: bodega (cuadro), parada (círculo numerado),
          pedido (rombo) y punto elegido (anillo). Aparecen con un pop en cascada. */}
      <g fontFamily="var(--font-mono)" fontSize={10} fontWeight={600}>
        {markers.map((m, i) => {
          const [x, y] = toXY(m);
          const pop = !reduce && i < MAX_CASCADE;
          const cls = pop ? "nm-pop" : undefined;
          const style = pop ? delayStyle(i, Math.min(markers.length, MAX_CASCADE), 0.6) : undefined;
          const text = m.kind === "depot" ? (m.label ?? "Bodega") : m.kind === "stop" ? `Parada ${m.label ?? ""}`.trim() : m.label;
          const interactive = m.kind !== "pick" && (!!text || !!props.onPick);
          const hoverProps = interactive
            ? {
                tabIndex: 0,
                role: props.onPick ? "button" as const : "img" as const,
                "aria-label": text ?? "Elegir ubicación",
                className: "nm-marker",
                style: { pointerEvents: "auto" as const },
                onMouseEnter: () => setTip(m.id),
                onMouseLeave: () => setTip((t) => (t === m.id ? null : t)),
                onFocus: () => setTip(m.id),
                onBlur: () => setTip((t) => (t === m.id ? null : t)),
                onClick: (event: React.MouseEvent<SVGGElement>) => pickMarker(m, props.onPick, event),
                onKeyDown: (event: React.KeyboardEvent<SVGGElement>) => pickMarker(m, props.onPick, event),
              }
            : {};
          return (
            <g key={m.id} {...hoverProps}>
              <g className={cls} style={style}>
                {m.kind === "depot" ? (
                  <rect x={x - 8} y={y - 8} width={16} height={16} rx={3} fill="var(--color-ink)" stroke="var(--color-surface)" strokeWidth={2} />
                ) : m.kind === "dot" ? (
                  <rect x={x - 5} y={y - 5} width={10} height={10} rx={1.5} transform={`rotate(45 ${x} ${y})`}
                    fill="var(--color-accent)" stroke="var(--color-surface)" strokeWidth={2} />
                ) : m.kind === "pick" ? (
                  <>
                    <circle cx={x} cy={y} r={7} fill="var(--color-accent)" stroke="var(--color-surface)" strokeWidth={2.5} />
                    <circle cx={x} cy={y} r={2} fill="var(--color-surface)" />
                  </>
                ) : (
                  <>
                    <circle cx={x} cy={y} r={10} fill="var(--color-ink)" stroke="var(--color-surface)" strokeWidth={2} />
                    <text x={x} y={y + 3.5} textAnchor="middle" fill="var(--color-on-ink)">{m.label}</text>
                  </>
                )}
                {interactive ? <circle className="nm-ring" cx={x} cy={y} r={14} fill="none" stroke="var(--color-accent)" strokeWidth={2} opacity={0} /> : null}
              </g>
            </g>
          );
        })}
      </g>

      {/* Tooltip propio (nombre) del marcador con el cursor o el foco */}
      {markers.map((m) => {
        if (tip !== m.id) return null;
        const text = m.kind === "depot" ? (m.label ?? "Bodega") : m.kind === "stop" ? `Parada ${m.label ?? ""}`.trim() : m.label;
        if (!text) return null;
        const [x, y] = toXY(m);
        const w = Math.max(28, text.length * 6.2 + 14);
        return (
          <g key={`tip-${m.id}`} className={reduce ? undefined : "nm-fade"} pointerEvents="none" fontFamily="var(--font-sans)">
            <rect x={x - w / 2} y={y - 40} width={w} height={22} rx={6} fill="var(--color-ink)" />
            <path d={`M${x - 4},${y - 18} L${x},${y - 13} L${x + 4},${y - 18} Z`} fill="var(--color-ink)" />
            <text x={x} y={y - 25} textAnchor="middle" fontSize={11} fontWeight={500} fill="var(--color-on-ink)">{text}</text>
          </g>
        );
      })}
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

function GoogleNetworkMap(props: NetworkMapProps) {
  const { nodes, width = 640, height = 720, fitTo, onPick, fill, className, ariaLabel = "Mapa de la red vial de Guatemala" } = props;
  const divRef = React.useRef<HTMLDivElement>(null);
  const { resolved: theme } = useTheme();
  const [map, setMap] = React.useState<google.maps.Map | null>(null);
  const [overlay, setOverlay] = React.useState<google.maps.OverlayView | null>(null);
  const [, redraw] = React.useReducer((x: number) => x + 1, 0);

  // Crear el mapa una sola vez
  React.useEffect(() => {
    if (!divRef.current) return;
    const m = new google.maps.Map(divRef.current, {
      center: GUATEMALA_CENTER,
      zoom: 7,
      styles: mapStyles(theme),
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

  // Cambio de tema: el mapa base sigue el modo claro/oscuro
  React.useEffect(() => {
    map?.setOptions({ styles: mapStyles(theme) });
  }, [map, theme]);

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
        <svg className="pointer-events-none absolute inset-0 size-full select-none" role="group" aria-label="Marcadores del mapa">
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
