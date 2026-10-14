import type { LatLng } from "./geo";
import { decodePolyline, type EdgeGeometry } from "./polyline";
import type { Band, DayType } from "./traffic";
import type { TrafficProfile } from "./trafficLevel";

/** Solo perfiles vigentes y calibrados; conserva ambos sentidos como tramos distintos. */
export function trafficMapEdges(profile: TrafficProfile | undefined, band: Band, day: DayType) {
  if (!profile?.calibrated || profile.band !== band || profile.day_type !== day) return null;
  return profile.edges.flatMap((edge) =>
    edge.from && edge.to && Number.isFinite(edge.multiplier) && edge.multiplier >= 1
      ? [{ from: edge.from, to: edge.to, multiplier: edge.multiplier }] : []);
}

export interface TrafficPair {
  /** Clave estable del par no dirigido ("a>b" con a < b). */
  key: string;
  a: string;
  b: string;
  /** Multiplicador mayor entre ambos sentidos: define el color. */
  multiplier: number;
  /** Multiplicadores por sentido (null si no hay dato en ese sentido). */
  ab: number | null;
  ba: number | null;
}

/** Un solo trazo por par de nodos: combina los dos sentidos y conserva el peor. */
export function mergeTrafficPairs(edges: { from: string; to: string; multiplier: number }[] | null): TrafficPair[] {
  const pairs = new Map<string, TrafficPair>();
  for (const edge of edges ?? []) {
    const forward = edge.from < edge.to;
    const [a, b] = forward ? [edge.from, edge.to] : [edge.to, edge.from];
    const key = `${a}>${b}`;
    const pair = pairs.get(key) ?? { key, a, b, multiplier: 1, ab: null, ba: null };
    if (forward) pair.ab = Math.max(pair.ab ?? 0, edge.multiplier);
    else pair.ba = Math.max(pair.ba ?? 0, edge.multiplier);
    pair.multiplier = Math.max(pair.multiplier, edge.multiplier);
    pairs.set(key, pair);
  }
  return [...pairs.values()];
}

/** Pares de nodos (en ambos sentidos) cuya geometría hay que pedir al servidor. */
export function geometryPairsFor(pairs: TrafficPair[]): string[][] {
  return pairs.flatMap((pair) => [[pair.a, pair.b], [pair.b, pair.a]]);
}

/** Texto del tooltip: ambos sentidos si difieren, uno solo si coinciden. */
export function pairTitle(pair: TrafficPair, names: (code: string) => string): string {
  const a = names(pair.a);
  const b = names(pair.b);
  if (pair.ab !== null && pair.ba !== null && pair.ab !== pair.ba) {
    return `${a} → ${b}: ×${pair.ab} · ${b} → ${a}: ×${pair.ba}`;
  }
  return `${a} ↔ ${b}: ×${pair.multiplier}`;
}

export interface DrawnPair { pair: TrafficPair; points: LatLng[] }

/**
 * Qué dibujar sobre Google: solo pares con geometría guardada (nada de rectas sobre
 * el mapa real). Usa la polilínea a→b o, si falta, la b→a invertida.
 */
export function pairsWithGeometry(pairs: TrafficPair[], geometry: EdgeGeometry[]): DrawnPair[] {
  const byPair = new Map(geometry.map((edge) => [`${edge.from}>${edge.to}`, edge.polyline]));
  const drawn: DrawnPair[] = [];
  for (const pair of pairs) {
    try {
      const forward = byPair.get(`${pair.a}>${pair.b}`);
      const backward = byPair.get(`${pair.b}>${pair.a}`);
      const points = forward ? decodePolyline(forward) : backward ? decodePolyline(backward).reverse() : null;
      if (points && points.length >= 2) drawn.push({ pair, points });
    } catch {
      // Polilínea inválida: se omite ese tramo.
    }
  }
  return drawn;
}

export const GEOMETRY_PENDING_NOTE = "Nuestro tráfico se mostrará sobre las carreteras cuando se cargue la geometría de la red.";

/** Interruptores excluyentes: encender uno apaga el otro para que no se encimen. */
export function toggleLayer(state: { google: boolean; ours: boolean }, layer: "google" | "ours") {
  if (state[layer]) return { ...state, [layer]: false };
  return layer === "google" ? { google: true, ours: false } : { google: false, ours: true };
}

/** Clave única de la geometría de toda la red: una sola solicitud compartida por todos los mapas. */
export const NETWORK_GEOMETRY_KEY = ["network-geometry"] as const;
