import type { LatLng } from "./geo";

export interface EdgeGeometry { from: string; to: string; polyline: string }

/** Decodifica el formato de Google sin cargar su librería geometry. */
export function decodePolyline(encoded: string): LatLng[] {
  let index = 0;
  let lat = 0;
  let lng = 0;
  const points: LatLng[] = [];
  function delta() {
    let value = 0;
    let factor = 1;
    let byte: number;
    do {
      if (index >= encoded.length || factor > 2 ** 30) throw new Error("Polilínea inválida.");
      byte = encoded.charCodeAt(index++) - 63;
      if (byte < 0 || byte > 63) throw new Error("Polilínea inválida.");
      value += (byte & 31) * factor;
      factor *= 32;
    } while (byte >= 32);
    return value % 2 ? -(Math.floor(value / 2) + 1) : value / 2;
  }
  while (index < encoded.length) {
    lat += delta();
    lng += delta();
    if (Math.abs(lat) > 9_000_000 || Math.abs(lng) > 18_000_000) throw new Error("Polilínea inválida.");
    points.push({ lat: lat / 1e5, lng: lng / 1e5 });
  }
  return points;
}

/** Toda la ruta debe estar completa: nunca mezcla aristas distintas con un respaldo. */
export function concatenateGeometry(codes: string[], edges: EdgeGeometry[]): LatLng[] | null {
  if (codes.length < 2) return null;
  const byPair = new Map(edges.map((edge) => [`${edge.from}>${edge.to}`, edge.polyline]));
  const result: LatLng[] = [];
  try {
    for (let i = 1; i < codes.length; i++) {
      const encoded = byPair.get(`${codes[i - 1]}>${codes[i]}`);
      if (!encoded) return null;
      const points = decodePolyline(encoded);
      if (points.length < 2) return null;
      const last = result.at(-1);
      if (last && last.lat === points[0].lat && last.lng === points[0].lng) points.shift();
      result.push(...points);
    }
    return result;
  } catch {
    return null;
  }
}
