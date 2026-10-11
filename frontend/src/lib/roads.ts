/**
 Funciones puras para dibujar rutas por carretera real.

 El CAMINO (qué nodos se recorren) lo decide nuestro Dijkstra / A*; Google Directions solo
 dibuja por dónde va la carretera entre esos puntos. Directions acepta como máximo 25 puntos
 intermedios por solicitud, así que si la ruta trae más nodos se submuestrea de forma pareja.
*/

/** Máximo de waypoints intermedios que acepta Directions en una solicitud. */
export const MAX_WAYPOINTS = 25;

/**
 Reduce `points` a lo más `maxIntermediate + 2` puntos (origen + intermedios + destino),
 repartidos de forma pareja y manteniendo siempre el primero y el último en orden.
 */
export function sampleWaypoints<T>(points: T[], maxIntermediate = MAX_WAYPOINTS): T[] {
  const limit = Math.max(0, Math.floor(maxIntermediate)) + 2;
  if (points.length <= limit) return points.slice();
  const last = points.length - 1;
  const picked: T[] = [];
  for (let i = 0; i < limit; i += 1) picked.push(points[Math.round((i * last) / (limit - 1))]);
  return picked;
}

/** Distancia en metros entre dos puntos (haversine); solo para decidir si vale la pena dibujar un tramo. */
export function distanceMeters(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const rad = Math.PI / 180;
  const dLat = (b.lat - a.lat) * rad;
  const dLng = (b.lng - a.lng) * rad;
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(a.lat * rad) * Math.cos(b.lat * rad) * Math.sin(dLng / 2) ** 2;
  return 2 * 6371000 * Math.asin(Math.min(1, Math.sqrt(h)));
}

/**
 Qué nodos del camino se le pasan a Directions como puntos de guía.

 Respaldo mientras las aristas no tienen polilínea guardada (RUT-75). Los nodos de municipio y
 cabecera están en el centro del pueblo, normalmente fuera de la carretera: si Directions debe
 pasar por cada uno, hace lazos para entrar y salir (Villa Nueva, Cocales, Siquinalá...). Por eso
 solo se guía por el origen, el destino, las PARADAS reales y, como mucho, los nodos de tipo
 "cruce" (están sobre la carretera) para que Google no tome otra autopista en tramos largos.
 Nunca por cabeceras ni municipios intermedios.
*/
export function guideCodes(codes: string[], stopCodes: string[], kindOf: (code: string) => string | undefined): string[] {
  const stops = new Set(stopCodes);
  const last = codes.length - 1;
  return codes.filter((code, i) => i === 0 || i === last || stops.has(code) || kindOf(code) === "cruce");
}

/** Un tramo propio (nodo a punto real) solo se dibuja si el punto real queda a más de `minMeters` del nodo. */
export function needsConnector(from: { lat: number; lng: number }, to: { lat: number; lng: number }, minMeters = 400): boolean {
  return distanceMeters(from, to) > minMeters;
}

export interface Connector {
  id: string;
  from: { lat: number; lng: number };
  to: { lat: number; lng: number };
}

/**
 Tramos de conexión de una ruta: bodega a su nodo (primero) y nodo de cada parada a las
 coordenadas reales del pedido. Se omiten los que no hacen falta (el punto ya está en el nodo)
 o los pedidos sin coordenadas.
*/
export function routeConnectors(
  depot: { lat: number; lng: number } | null,
  depotNode: { lat: number; lng: number } | null,
  stops: { id: number | string; lat: number | null; lng: number | null; node: { lat: number; lng: number } | null }[],
): Connector[] {
  const out: Connector[] = [];
  if (depot && depotNode && needsConnector(depotNode, depot)) out.push({ id: "depot", from: depot, to: depotNode });
  for (const s of stops) {
    if (s.lat == null || s.lng == null || !s.node) continue;
    const real = { lat: s.lat, lng: s.lng };
    if (needsConnector(s.node, real)) out.push({ id: `stop-${s.id}`, from: s.node, to: real });
  }
  return out;
}

/** Une los nodos de varios tramos consecutivos sin repetir el nodo donde empalman. */
export function joinLegNodes(legs: { nodes: string[] }[]): string[] {
  const out: string[] = [];
  for (const leg of legs) {
    for (const code of leg.nodes) {
      if (out[out.length - 1] !== code) out.push(code);
    }
  }
  return out;
}
