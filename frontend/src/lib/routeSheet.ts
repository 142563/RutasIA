import type { RouteStopRow } from "./dispatch";
import type { Order } from "./types";

/** Conserva el orden de visita y distingue un pedido ausente de una referencia vacía. */
export function routeSheetStops(stops: RouteStopRow[], orders: Pick<Order, "code" | "reference">[]) {
  const byCode = new Map(orders.map((order) => [order.code, order]));
  return [...stops].sort((a, b) => a.sequence - b.sequence).map((stop) => ({
    ...stop,
    reference: byCode.get(stop.order_code)?.reference ?? null,
  }));
}
