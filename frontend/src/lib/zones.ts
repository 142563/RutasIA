import type { Order } from "./types";

/** Pedidos pendientes agrupados por región de Guatemala: la forma más rápida de armar una ruta con sentido. */
export interface Zone {
  code: string;
  name: string;
  orderIds: number[];
  weightKg: number;
  places: string[];
}

export function groupByZone(orders: Order[]): Zone[] {
  const zones = new Map<string, Zone>();
  for (const o of orders) {
    const code = o.region?.code ?? "?";
    const zone = zones.get(code) ?? { code, name: o.region?.name ?? "Sin región", orderIds: [], weightKg: 0, places: [] };
    zone.orderIds.push(o.id);
    zone.weightKg += o.weight_kg;
    const place = o.node?.name.split(" (")[0];
    if (place && !zone.places.includes(place)) zone.places.push(place);
    zones.set(code, zone);
  }
  // Primero las zonas con más pedidos; a igualdad, por nombre
  return [...zones.values()].sort((a, b) => b.orderIds.length - a.orderIds.length || a.name.localeCompare(b.name));
}

/** "Mixco, Antigua y 2 más" */
export function placesLabel(places: string[], max = 3): string {
  if (places.length <= max) return places.join(", ");
  return `${places.slice(0, max).join(", ")} y ${places.length - max} más`;
}
