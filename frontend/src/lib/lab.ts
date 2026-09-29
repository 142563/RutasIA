/** Lógica pura del Laboratorio: animación sincronizada de dos búsquedas. */
import { BAND_TIME, type Band, type DayType } from "./traffic";

/** Nodos visibles de una búsqueda en el paso `step` (ambas avanzan al mismo ritmo). */
export function visibleOrder(order: string[], step: number): string[] {
  return order.slice(0, Math.max(0, Math.min(step, order.length)));
}

/** Pasos totales: la animación termina cuando termina la búsqueda más larga. */
export function totalSteps(...orders: string[][]): number {
  return Math.max(0, ...orders.map((o) => o.length));
}

export function isFinished(order: string[], step: number): boolean {
  return step >= order.length;
}

/** Porcentaje de nodos que A* se ahorra frente a Dijkstra (entero, 0 si no aplica). */
export function savingPct(dijkstraExpanded: number, astarExpanded: number): number {
  if (dijkstraExpanded <= 0) return 0;
  return Math.round((1 - astarExpanded / dijkstraExpanded) * 100);
}

/**
 Salida representativa (hora de Guatemala) para una franja y tipo de día:
 el próximo martes (laboral) o sábado (fin de semana), igual que la calibración.
*/
export function departureFor(band: Band, dayType: DayType, now = new Date()): string {
  const gt = new Date(now.getTime() - 6 * 60 * 60 * 1000); // "reloj" de Guatemala en UTC
  const target = dayType === "weekday" ? 2 : 6; // martes / sábado
  const days = ((target - gt.getUTCDay() + 7) % 7) || 7;
  const day = new Date(gt.getTime() + days * 24 * 60 * 60 * 1000);
  return `${day.toISOString().slice(0, 10)}T${BAND_TIME[band]}`;
}
