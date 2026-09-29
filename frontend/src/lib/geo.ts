/** Proyección simple lat/lon → SVG para el mapa esquemático de Guatemala.

 Equirectangular con corrección cos(latitud media): a la escala de un país
 (~4° de latitud) la deformación es despreciable y las distancias en pantalla
 son proporcionales a las reales.
*/

export interface LatLng {
  lat: number;
  lng: number;
}

export interface Projection {
  width: number;
  height: number;
  toXY(point: LatLng): [number, number];
  toLatLng(x: number, y: number): LatLng;
}

export function makeProjection(points: LatLng[], width: number, height: number, padding = 24, minSpanDeg = 0): Projection {
  const lats = points.map((p) => p.lat);
  const lngs = points.map((p) => p.lng);
  let minLat = Math.min(...lats);
  let maxLat = Math.max(...lats);
  let minLng = Math.min(...lngs);
  let maxLng = Math.max(...lngs);
  // Evita acercar de más cuando hay pocos puntos juntos (p. ej. una ruta corta)
  if (maxLat - minLat < minSpanDeg) {
    const c = (minLat + maxLat) / 2;
    [minLat, maxLat] = [c - minSpanDeg / 2, c + minSpanDeg / 2];
  }
  if (maxLng - minLng < minSpanDeg) {
    const c = (minLng + maxLng) / 2;
    [minLng, maxLng] = [c - minSpanDeg / 2, c + minSpanDeg / 2];
  }
  const kx = Math.cos((((minLat + maxLat) / 2) * Math.PI) / 180);

  const spanX = Math.max((maxLng - minLng) * kx, 1e-9);
  const spanY = Math.max(maxLat - minLat, 1e-9);
  const scale = Math.min((width - 2 * padding) / spanX, (height - 2 * padding) / spanY);
  // Centrar el contenido en el área disponible
  const offsetX = (width - spanX * scale) / 2;
  const offsetY = (height - spanY * scale) / 2;

  return {
    width,
    height,
    toXY: ({ lat, lng }) => [offsetX + (lng - minLng) * kx * scale, offsetY + (maxLat - lat) * scale],
    toLatLng: (x, y) => ({
      lng: minLng + (x - offsetX) / (kx * scale),
      lat: maxLat - (y - offsetY) / scale,
    }),
  };
}
