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

export function makeProjection(points: LatLng[], width: number, height: number, padding = 24): Projection {
  const lats = points.map((p) => p.lat);
  const lngs = points.map((p) => p.lng);
  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs);
  const maxLng = Math.max(...lngs);
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
