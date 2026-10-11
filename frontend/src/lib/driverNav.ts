import type { LatLng } from "./geo";
import type { DriverRouteMap, DriverStop } from "./driver";

/** Distancia en línea recta entre dos puntos (km). */
export function haversineKm(a: LatLng, b: LatLng): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371 * Math.asin(Math.min(1, Math.sqrt(h)));
}

/** Nodos de los tramos que faltan: del que llega a la parada actual en adelante, sin repetir empalmes. */
export function remainingCodes(map: Pick<DriverRouteMap, "legs"> | undefined, nextSequence: number): string[] {
  const out: string[] = [];
  for (const leg of map?.legs ?? []) {
    if (leg.to_sequence < nextSequence) continue;
    for (const code of leg.nodes) if (out[out.length - 1] !== code) out.push(code);
  }
  return out;
}

/** Pares únicos (en orden) que NetworkMap pide como geometría; sirve para precargar su caché. */
export function geometryPairs(codes: string[]): string[][] {
  const pairs = new Map<string, string[]>();
  codes.slice(1).forEach((to, i) => pairs.set(`${codes[i]}>${to}`, [codes[i], to]));
  return [...pairs.values()];
}

/**
 * "Llegas en N min" simple: línea recta × 1.3 (la carretera da vueltas) a la velocidad actual
 * (entre 15 y 60 km/h; 35 si el GPS no la da). Sin posición, se usa la hora estimada de la parada.
 */
export function minutesToStop(
  position: LatLng | null,
  speedKmh: number | null,
  stop: Pick<DriverStop, "lat" | "lng" | "eta">,
  now = new Date(),
): number | null {
  if (position && stop.lat != null && stop.lng != null) {
    const speed = Math.min(60, Math.max(15, speedKmh ?? 35));
    return Math.max(1, Math.round(((haversineKm(position, { lat: stop.lat, lng: stop.lng }) * 1.3) / speed) * 60));
  }
  const diff = (new Date(stop.eta).getTime() - now.getTime()) / 60_000;
  return Number.isFinite(diff) ? Math.max(1, Math.round(diff)) : null;
}

export function formatDistance(km: number): string {
  return km < 1 ? `${Math.round(km * 10) * 100} m` : `${km.toFixed(km < 10 ? 1 : 0)} km`;
}
