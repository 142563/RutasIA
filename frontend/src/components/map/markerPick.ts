import type { LatLng } from "@/lib/geo";

interface ActivationEvent {
  key?: string;
  stopPropagation: () => void;
  preventDefault: () => void;
}

/** El marcador elige su ubicación una sola vez, también con Enter o Espacio. */
export function pickMarker(point: LatLng, onPick: ((point: LatLng) => void) | undefined, event: ActivationEvent) {
  if (!onPick || (event.key !== undefined && event.key !== "Enter" && event.key !== " ")) return;
  event.stopPropagation();
  if (event.key !== undefined) event.preventDefault();
  onPick({ lat: point.lat, lng: point.lng });
}
