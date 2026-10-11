import type { LatLng } from "./geo";

/** Solo interpola el marcador entre mediciones; no estima la posición real. */
export function interpolatePosition(from: LatLng, to: LatLng, progress: number): LatLng {
  const fraction = Math.max(0, Math.min(1, Number.isFinite(progress) ? progress : 0));
  const delta = ((to.lng - from.lng + 540) % 360) - 180;
  return { lat: from.lat + (to.lat - from.lat) * fraction,
    lng: ((from.lng + delta * fraction + 540) % 360) - 180 };
}
