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
